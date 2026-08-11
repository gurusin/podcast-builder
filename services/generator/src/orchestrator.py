"""Generator orchestrator — drives the end-to-end podcast generation pipeline."""

import asyncio
import logging
import os

from src.factories.base import BasePodcastGeneratorFactory
from src.repositories.base import BaseFilteredContentRepository, BasePodcastMetaRepository
from src.events.kafka_producer import KafkaProducer

logger = logging.getLogger(__name__)

_DEFAULT_DURATION_HINT = "medium"


class GeneratorOrchestrator:
    """
    Coordinates script writing, TTS synthesis, status persistence, and
    event publishing for a single podcast.
    """

    def __init__(
        self,
        factory: BasePodcastGeneratorFactory,
        filtered_content_repo: BaseFilteredContentRepository,
        podcast_meta_repo: BasePodcastMetaRepository,
        kafka_producer: KafkaProducer,
        podcasts_dir: str,
    ) -> None:
        self._factory = factory
        self._filtered_content_repo = filtered_content_repo
        self._podcast_meta_repo = podcast_meta_repo
        self._kafka_producer = kafka_producer
        self._podcasts_dir = podcasts_dir

    async def process(self, event: dict) -> None:
        """
        Handle a single ContentReady event end-to-end.

        Steps:
          1. Mark the podcast as GENERATING.
          2. Load filtered content from MongoDB.
          3. Resolve topic and duration_hint from the podcasts collection.
          4. Create writer + TTS engine via the factory.
          5. Build the script and synthesize audio.
          6. Mark the podcast as DONE and publish PodcastGenerated.
          7. On any error, mark as FAILED and re-raise.

        Args:
            event: Deserialised ContentReady Kafka event dict.

        Raises:
            ValueError: If the filtered_content document is missing.
            Exception: Any underlying error after FAILED status is recorded.
        """
        podcast_id: str = event["podcastId"]
        logger.info("GeneratorOrchestrator: processing podcastId=%s", podcast_id)

        # Step 1 — mark as GENERATING
        await self._podcast_meta_repo.update_status(podcast_id, "GENERATING")

        try:
            # Step 2 — load filtered content
            content_doc = await self._filtered_content_repo.find_by_podcast_id(podcast_id)
            if content_doc is None:
                raise ValueError(
                    f"No filtered_content document found for podcastId={podcast_id}"
                )

            chunks: list[dict] = content_doc.get("chunks", [])

            # Step 3 — resolve topic and duration_hint from the podcasts collection
            podcast_doc = await self._podcast_meta_repo.find_by_podcast_id(podcast_id)
            if podcast_doc is not None:
                topic: str = podcast_doc.get("topic") or (
                    chunks[0].get("title") if chunks else podcast_id
                )
                duration_hint: str = podcast_doc.get("durationHint", _DEFAULT_DURATION_HINT)
            else:
                # Graceful fallback: use first chunk title or podcastId
                topic = chunks[0].get("title") if chunks else podcast_id
                duration_hint = _DEFAULT_DURATION_HINT

            # Step 4 — create writer and TTS engine via Abstract Factory
            script_writer = self._factory.create_script_writer()
            tts_engine = self._factory.create_tts_engine()

            # Step 5 — build script
            script = script_writer.write(topic, chunks, duration_hint)
            logger.debug(
                "GeneratorOrchestrator: script for podcastId=%s has %d chars",
                podcast_id,
                len(script),
            )

            # Step 6 — synthesize audio (run in thread to avoid blocking the event loop)
            output_path = os.path.join(self._podcasts_dir, f"{podcast_id}.mp3")
            loop = asyncio.get_event_loop()
            duration_secs = await loop.run_in_executor(
                None, tts_engine.synthesize, script, output_path
            )
            logger.info(
                "GeneratorOrchestrator: synthesized %s (%.1fs)", output_path, duration_secs
            )

            # Step 7 — mark as DONE
            await self._podcast_meta_repo.update_status(podcast_id, "DONE", output_path)

            # Step 8 — publish PodcastGenerated event
            await self._kafka_producer.publish_podcast_generated(
                podcast_id, output_path, duration_secs
            )
            logger.info("GeneratorOrchestrator: completed podcastId=%s", podcast_id)

        except Exception as exc:
            logger.exception(
                "GeneratorOrchestrator: failed for podcastId=%s: %s", podcast_id, exc
            )
            await self._podcast_meta_repo.update_status(podcast_id, "FAILED")
            raise
