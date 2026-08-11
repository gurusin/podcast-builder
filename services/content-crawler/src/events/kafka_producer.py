"""KafkaProducer — publishes JSON messages to Kafka topics.

Uses ``aiokafka.AIOKafkaProducer`` with UTF-8 JSON serialisation.
The producer is started lazily on the first ``publish`` call and stopped
explicitly via ``stop()``.  Both lifecycle methods are idempotent —
calling them multiple times is safe.
"""
import json
import logging
import os

from aiokafka import AIOKafkaProducer as _AIOKafkaProducer

logger = logging.getLogger(__name__)

_KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")


class KafkaProducer:
    """Async Kafka producer with lazy start.

    Parameters
    ----------
    broker:
        Kafka bootstrap server address.  Defaults to the ``KAFKA_BROKER``
        environment variable (fallback: ``kafka:9092``).
    """

    def __init__(self, broker: str = _KAFKA_BROKER) -> None:
        self._broker = broker
        self._producer: _AIOKafkaProducer | None = None

    async def _ensure_started(self) -> None:
        """Start the underlying producer if it has not been started yet."""
        if self._producer is None:
            self._producer = _AIOKafkaProducer(
                bootstrap_servers=self._broker,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
            logger.info(
                "KafkaProducer connected to broker %s", self._broker
            )

    async def publish(self, topic: str, message_dict: dict) -> None:
        """Serialise *message_dict* as JSON and send it to *topic*.

        Parameters
        ----------
        topic:
            Kafka topic name.
        message_dict:
            Payload to serialise and publish.
        """
        await self._ensure_started()
        await self._producer.send_and_wait(topic, message_dict)
        logger.debug(
            "Published message to topic %r: %s", topic, message_dict
        )

    async def stop(self) -> None:
        """Flush and close the underlying Kafka producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("KafkaProducer stopped.")
