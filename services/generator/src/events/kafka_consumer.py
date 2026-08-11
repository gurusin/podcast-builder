"""Kafka consumer — subscribes to content-ready and drives the orchestrator."""

import json
import logging

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)

_TOPIC = "content-ready"
_GROUP_ID = "generator-group"


class KafkaConsumer:
    """
    Subscribes to the content-ready Kafka topic and dispatches events
    to the GeneratorOrchestrator.
    """

    def __init__(self, broker: str, orchestrator) -> None:
        """
        Args:
            broker: Kafka bootstrap server address (host:port).
            orchestrator: Instance with an async `process(event: dict)` method.
        """
        self._broker = broker
        self._orchestrator = orchestrator
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Create and start the underlying AIOKafkaConsumer."""
        self._consumer = AIOKafkaConsumer(
            _TOPIC,
            bootstrap_servers=self._broker,
            group_id=_GROUP_ID,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self._consumer.start()
        logger.info(
            "KafkaConsumer: started (broker=%s, topic=%s, group=%s)",
            self._broker,
            _TOPIC,
            _GROUP_ID,
        )

    async def stop(self) -> None:
        """Stop the underlying AIOKafkaConsumer."""
        if self._consumer is not None:
            await self._consumer.stop()
            logger.info("KafkaConsumer: stopped")

    async def consume(self) -> None:
        """
        Poll messages in a loop and hand each event to the orchestrator.

        This coroutine runs indefinitely until the consumer is stopped or
        an unrecoverable error occurs.

        Raises:
            RuntimeError: If start() has not been called first.
        """
        if self._consumer is None:
            raise RuntimeError("KafkaConsumer.start() must be called before consume().")

        async for message in self._consumer:
            event: dict = message.value
            logger.info(
                "KafkaConsumer: received event eventType=%s podcastId=%s",
                event.get("eventType"),
                event.get("podcastId"),
            )
            try:
                await self._orchestrator.process(event)
            except Exception as exc:  # noqa: BLE001
                # Log and continue — a single failed event must not crash the loop.
                logger.exception(
                    "KafkaConsumer: orchestrator raised for podcastId=%s: %s",
                    event.get("podcastId"),
                    exc,
                )
