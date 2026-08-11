"""Entry point for the content-crawler microservice.

Bootstraps the DI container, wires it to the service modules, and starts
the :class:`~src.events.kafka_consumer.KafkaConsumer` which drives the
end-to-end crawl-filter-publish pipeline.

Run with::

    python -m src.main

or via the Dockerfile ``CMD``.
"""
import asyncio
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialise the container and start the Kafka consumer loop."""
    # Import here to avoid circular imports before the container is wired
    from src.container import Container  # noqa: PLC0415

    container = Container()
    container.wire(
        modules=[
            "src.orchestrator",
            "src.events.kafka_consumer",
            "src.events.kafka_producer",
        ]
    )

    logger.info(
        "Content-crawler service starting up. "
        "KAFKA_BROKER=%s MONGODB_URI=%s",
        os.environ.get("KAFKA_BROKER", "kafka:9092"),
        os.environ.get("MONGODB_URI", "mongodb://mongo:27017/podcast-system"),
    )

    consumer = container.kafka_consumer()
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
