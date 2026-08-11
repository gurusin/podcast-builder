"""Dependency Injection container (dependency-injector library)."""

import os

from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient

from src.factories.standard_factory import StandardPodcastGeneratorFactory
from src.factories.mock_factory import MockPodcastGeneratorFactory
from src.repositories.filtered_content_repository import FilteredContentRepository
from src.repositories.podcast_meta_repository import PodcastMetaRepository
from src.events.kafka_producer import KafkaProducer
from src.orchestrator import GeneratorOrchestrator

_GENERATOR_MODE_MOCK = "mock"
_DEFAULT_DB_NAME = "podcast-system"


def _build_factory(mode: str):
    """Return the appropriate concrete factory based on GENERATOR_MODE env var."""
    if mode == _GENERATOR_MODE_MOCK:
        return MockPodcastGeneratorFactory()
    return StandardPodcastGeneratorFactory()


def _resolve_db(client: AsyncIOMotorClient, uri: str):
    """
    Return the motor database.

    If the URI ends with a database name (e.g. .../podcast-system), use
    get_default_database(); otherwise fall back to _DEFAULT_DB_NAME.
    """
    db_name = uri.rsplit("/", 1)[-1].split("?")[0]
    if db_name:
        return client.get_default_database()
    return client[_DEFAULT_DB_NAME]


class Container(containers.DeclarativeContainer):
    """Wire all generator service dependencies together."""

    # ------------------------------------------------------------------ config
    config = providers.Configuration()

    # ---------------------------------------------------------- MongoDB client
    mongo_client = providers.Singleton(
        AsyncIOMotorClient,
        config.mongodb_uri,
    )

    mongo_db = providers.Singleton(
        _resolve_db,
        client=mongo_client,
        uri=config.mongodb_uri,
    )

    # ----------------------------------------------------------- Repositories
    filtered_content_repo = providers.Singleton(
        FilteredContentRepository,
        db=mongo_db,
    )

    podcast_meta_repo = providers.Singleton(
        PodcastMetaRepository,
        db=mongo_db,
    )

    # --------------------------------------------------------- Kafka producer
    kafka_producer = providers.Singleton(
        KafkaProducer,
        broker=config.kafka_broker,
    )

    # ----------------------------------------------------- Abstract Factory
    generator_factory = providers.Singleton(
        _build_factory,
        mode=config.generator_mode,
    )

    # ---------------------------------------------------------- Orchestrator
    orchestrator = providers.Singleton(
        GeneratorOrchestrator,
        factory=generator_factory,
        filtered_content_repo=filtered_content_repo,
        podcast_meta_repo=podcast_meta_repo,
        kafka_producer=kafka_producer,
        podcasts_dir=config.podcasts_dir,
    )
