"""Kafka producer — publishes podcast-generated events."""

import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

_TOPIC = "podcast-generated"
_EVENT_TYPE = "PodcastGenerated"
_VERSION = "1.0"


class KafkaProducer:
    """Wraps AIOKafkaProducer and publishes PodcastGenerated events."""

    def __init__(self, broker: str) -> None:
        self._broker = broker
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Start the underlying Kafka producer."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._broker,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._producer.start()
        logger.info("KafkaProducer: started (broker=%s)", self._broker)

    async def stop(self) -> None:
        """Flush and stop the underlying Kafka producer."""
        if self._producer is not None:
            await self._producer.stop()
            logger.info("KafkaProducer: stopped")

    async def publish_podcast_generated(
        self,
        podcast_id: str,
        file_path: str,
        duration_secs: float,
    ) -> None:
        """
        Publish a PodcastGenerated event to the podcast-generated topic.

        Args:
            podcast_id: UUID of the podcast.
            file_path: Absolute path to the generated MP3 file.
            duration_secs: Duration of the generated audio.

        Raises:
            RuntimeError: If the producer has not been started.
        """
        if self._producer is None:
            raise RuntimeError("KafkaProducer.start() must be called before publishing.")

        payload = {
            "eventType": _EVENT_TYPE,
            "version": _VERSION,
            "podcastId": podcast_id,
            "filePath": file_path,
            "durationSecs": duration_secs,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }
        await self._producer.send_and_wait(_TOPIC, value=payload)
        logger.info(
            "KafkaProducer: published %s for podcastId=%s", _EVENT_TYPE, podcast_id
        )
