"""Generator orchestrator — drives the end-to-end podcast generation pipeline."""

import asyncio
import logging
import os

from src.factories.base import BasePodcastGeneratorFactory
from src.repositories.base import BaseFilteredContentRepository, BasePodcastMetaRepository
from src.events.kafka_producer import KafkaProducer
from src.validation.pipeline import ValidationPipeline
from src.validation.word_count_validator import WordCountValidator
from src.validation.banned_content_validator import BannedContentValidator
from src.validation.groundedness_validator import GroundednessValidator
from src.validation.llm_judge_validator import LLMJudgeValidator

logger = logging.getLogger(__name__)

_DEFAULT_DURATION_HINT = "medium"
_MAX_VALIDATION_RETRIES = 3

# On retry, expand the content limit passed to the writer so more source
# material is included — progressively relaxes the script to stay grounded.
_RETRY_CONTENT_MULTIPLIERS = [1.0, 1.5, 2.0]


def _build_validation_pipeline(duration_hint: str) -> ValidationPipeline:
    """Build the ordered validator funnel for a given duration hint.

    Order (cheapest → most expensive):
      1. WordCountValidator     — O(n) word split
      2. BannedContentValidator — regex scan
      3. GroundednessValidator  — TF-IDF cosine similarity
      4. LLMJudgeValidator      — Claude API call (disabled unless env var set)
    """
    return ValidationPipeline(validators=[
        WordCountValidator(duration_hint),
        BannedContentValidator(),
        GroundednessValidator(),
        LLMJudgeValidator(),
    ])


class GeneratorOrchestrator:
    """
    Coordinates script writing, validation, TTS synthesis, status
    persistence, and event publishing for a single podcast.

    Validation runs before TTS so bad scripts are caught before synthesis.
    A bounded retry loop adjusts generation parameters on validation failure.
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
          5. Generate script → validate → retry up to _MAX_VALIDATION_RETRIES.
          6. Synthesize validated script to audio.
          7. Mark the podcast as DONE and publish PodcastGenerated.
          8. On any unrecoverable error, mark as FAILED and re-raise.

        Args:
            event: Deserialised ContentReady Kafka event dict.
        """
        podcast_id: str = event["podcastId"]
        logger.info("GeneratorOrchestrator: processing podcastId=%s", podcast_id)

        await self._podcast_meta_repo.update_status(podcast_id, "GENERATING")

        try:
            content_doc = await self._filtered_content_repo.find_by_podcast_id(podcast_id)
            if content_doc is None:
                raise ValueError(
                    f"No filtered_content document found for podcastId={podcast_id}"
                )

            chunks: list[dict] = content_doc.get("chunks", [])

            podcast_doc = await self._podcast_meta_repo.find_by_podcast_id(podcast_id)
            if podcast_doc is not None:
                topic: str = podcast_doc.get("topic") or (
                    chunks[0].get("title") if chunks else podcast_id
                )
                duration_hint: str = podcast_doc.get("durationHint", _DEFAULT_DURATION_HINT)
            else:
                topic = chunks[0].get("title") if chunks else podcast_id
                duration_hint = _DEFAULT_DURATION_HINT

            script_writer = self._factory.create_script_writer()
            tts_engine = self._factory.create_tts_engine()
            validation_pipeline = _build_validation_pipeline(duration_hint)

            # --- Generate + Validate loop -----------------------------------
            script: str = ""
            last_critique: str = ""
            for attempt in range(1, _MAX_VALIDATION_RETRIES + 1):
                # On retry, pass the attempt number so the writer can relax
                # its content-limit to pull in more source material.
                script = script_writer.write(
                    topic, chunks, duration_hint, attempt=attempt
                )
                logger.debug(
                    "GeneratorOrchestrator: attempt %d/%d — script %d chars for podcastId=%s",
                    attempt, _MAX_VALIDATION_RETRIES, len(script), podcast_id,
                )

                result = validation_pipeline.validate(script, chunks, topic)
                logger.info(
                    "GeneratorOrchestrator: validation attempt %d/%d — passed=%s "
                    "validator=%s score=%.3f for podcastId=%s",
                    attempt, _MAX_VALIDATION_RETRIES,
                    result.passed, result.validator_name, result.score, podcast_id,
                )

                if result.passed:
                    break

                last_critique = result.critique
                if attempt == _MAX_VALIDATION_RETRIES:
                    raise ValueError(
                        f"Script validation failed after {_MAX_VALIDATION_RETRIES} attempts. "
                        f"Last failure: {last_critique}"
                    )

                logger.warning(
                    "GeneratorOrchestrator: retrying script generation (attempt %d/%d) — %s",
                    attempt, _MAX_VALIDATION_RETRIES, last_critique,
                )
            # ----------------------------------------------------------------

            output_path = os.path.join(self._podcasts_dir, f"{podcast_id}.mp3")
            loop = asyncio.get_event_loop()
            duration_secs = await loop.run_in_executor(
                None, tts_engine.synthesize, script, output_path
            )
            logger.info(
                "GeneratorOrchestrator: synthesized %s (%.1fs)", output_path, duration_secs
            )

            await self._podcast_meta_repo.update_status(podcast_id, "DONE", output_path)

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
