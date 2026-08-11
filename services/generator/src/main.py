"""Entry point for the Generator microservice."""

import asyncio
import logging
import os
import signal

from src.container import Container
from src.events.kafka_consumer import KafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ env vars
KAFKA_BROKER: str = os.getenv("KAFKA_BROKER", "kafka:9092")
MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://mongo:27017/podcast-system")
PODCASTS_DIR: str = os.getenv("PODCASTS_DIR", "/app/podcasts")
GENERATOR_MODE: str = os.getenv("GENERATOR_MODE", "standard")


async def main() -> None:
    """Bootstrap dependencies, then start consuming Kafka events."""

    # Ensure the podcast output directory exists.
    os.makedirs(PODCASTS_DIR, exist_ok=True)
    logger.info("Podcasts directory: %s", PODCASTS_DIR)

    # ---------------------------------------------- wire the DI container
    container = Container()
    container.config.kafka_broker.from_value(KAFKA_BROKER)
    container.config.mongodb_uri.from_value(MONGODB_URI)
    container.config.podcasts_dir.from_value(PODCASTS_DIR)
    container.config.generator_mode.from_value(GENERATOR_MODE)

    orchestrator = container.orchestrator()
    kafka_producer = container.kafka_producer()

    # ---------------------------------------------- start Kafka producer
    await kafka_producer.start()

    consumer = KafkaConsumer(broker=KAFKA_BROKER, orchestrator=orchestrator)
    await consumer.start()

    # ---------------------------------------------- graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: signal.Signals) -> None:
        logger.info("Received signal %s — shutting down", sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    logger.info("Generator service started. Waiting for events...")
    try:
        consume_task = asyncio.create_task(consumer.consume())
        stop_task = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait(
            {consume_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        await consumer.stop()
        await kafka_producer.stop()
        logger.info("Generator service stopped.")


if __name__ == "__main__":
    asyncio.run(main())
