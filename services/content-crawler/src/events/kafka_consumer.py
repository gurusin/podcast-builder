"""KafkaConsumer — subscribes to ``topic-requested`` and dispatches events.

Uses ``aiokafka.AIOKafkaConsumer`` with UTF-8 JSON deserialisation.
For each received message the consumer calls
``CrawlerOrchestrator.process(event)`` and commits the offset only after
successful processing.

Group ID: ``content-crawler-group``
Topic consumed: ``topic-requested``
"""
import json
import logging
import os

from aiokafka import AIOKafkaConsumer as _AIOKafkaConsumer

logger = logging.getLogger(__name__)

_KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
_KAFKA_GROUP_ID = "content-crawler-group"
_TOPIC_REQUESTED = "topic-requested"


class KafkaConsumer:
    """Async Kafka consumer that drives the :class:`~src.orchestrator.CrawlerOrchestrator`.

    Parameters
    ----------
    orchestrator:
        A :class:`~src.orchestrator.CrawlerOrchestrator` instance whose
        ``process`` coroutine is called for each incoming event.
    broker:
        Kafka bootstrap server address.
    """

    def __init__(self, orchestrator, broker: str = _KAFKA_BROKER) -> None:
        self._orchestrator = orchestrator
        self._broker = broker

    async def start(self) -> None:
        """Connect to Kafka and begin consuming ``topic-requested`` messages.

        This coroutine runs indefinitely (until the process is killed or an
        unrecoverable error occurs).  It commits offsets manually after each
        message is processed so that no event is silently skipped.
        """
        consumer = _AIOKafkaConsumer(
            _TOPIC_REQUESTED,
            bootstrap_servers=self._broker,
            group_id=_KAFKA_GROUP_ID,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
            enable_auto_commit=False,
        )

        await consumer.start()
        logger.info(
            "KafkaConsumer started — listening on topic %r (group %r)",
            _TOPIC_REQUESTED,
            _KAFKA_GROUP_ID,
        )

        try:
            async for message in consumer:
                event: dict = message.value
                logger.info(
                    "Received event: eventType=%r podcastId=%r",
                    event.get("eventType"),
                    event.get("podcastId"),
                )
                try:
                    await self._orchestrator.process(event)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Orchestrator failed for event %r: %s", event, exc
                    )
                finally:
                    await consumer.commit()
        finally:
            await consumer.stop()
            logger.info("KafkaConsumer stopped.")
