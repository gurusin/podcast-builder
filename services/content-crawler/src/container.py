"""Dependency Injection container (dependency-injector library).

``Container`` wires together every component of the content-crawler
service.  Callers import ``Container``, call ``container.wire(modules=[...])``,
and then use ``@inject`` or ``Provide[...]`` to receive dependencies.

Wired components
----------------
* ``KafkaProducer``              — singleton Kafka producer
* ``WebCrawlerFactory``          — singleton factory (stateless)
* ``WikipediaCrawlerFactory``    — singleton factory (stateless)
* ``RSSCrawlerFactory``          — singleton factory (stateless)
* ``motor_client``               — singleton Motor client
* ``motor_db``                   — singleton Motor database
* ``RawContentRepository``       — singleton, injected with ``motor_db``
* ``FilteredContentRepository``  — singleton, injected with ``motor_db``
* ``QualityFilter``              — singleton (stateless)
* ``DeduplicationFilter``        — singleton (stateless)
* ``RelevanceFilter``            — factory (topic injected per-request; see note)
* ``FilterPipeline``             — singleton with [quality, dedup, relevance]
* ``CrawlerOrchestrator``        — singleton, injected with all the above
* ``KafkaConsumer``              — singleton, injected with orchestrator

Note on RelevanceFilter
~~~~~~~~~~~~~~~~~~~~~~~
``RelevanceFilter`` requires the runtime ``topic`` string.  In the DI
container it is registered as a factory provider so the orchestrator can
instantiate it with the correct topic at call time.  The ``FilterPipeline``
singleton is built with a *placeholder* ``RelevanceFilter("")`` by default;
the orchestrator is responsible for rebuilding the pipeline with the live
topic when needed.  For simplicity in this microservice the pipeline is
rebuilt inside ``CrawlerOrchestrator.process`` using the topic from the
event — the container provides all other strategies as singletons.
"""
import os

from dependency_injector import containers, providers
from pymongo import AsyncMongoClient

from src.events.kafka_consumer import KafkaConsumer
from src.events.kafka_producer import KafkaProducer
from src.factories.content_source_factory import (
    RSSCrawlerFactory,
    WebCrawlerFactory,
    WikipediaCrawlerFactory,
)
from src.filters.deduplication_filter import DeduplicationFilter
from src.filters.filter_pipeline import FilterPipeline
from src.filters.quality_filter import QualityFilter
from src.filters.relevance_filter import RelevanceFilter
from src.orchestrator import CrawlerOrchestrator
from src.repositories.filtered_content_repository import FilteredContentRepository
from src.repositories.podcast_status_repository import PodcastStatusRepository
from src.repositories.raw_content_repository import RawContentRepository

_KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
_MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://mongo:27017/podcast-system")
_DB_NAME = _MONGODB_URI.rsplit("/", 1)[-1]


class Container(containers.DeclarativeContainer):
    """Top-level DI container for the content-crawler service."""

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------

    kafka_producer: providers.Singleton = providers.Singleton(
        KafkaProducer,
        broker=_KAFKA_BROKER,
    )

    motor_client: providers.Singleton = providers.Singleton(
        AsyncMongoClient,
        _MONGODB_URI,
    )

    motor_db: providers.Singleton = providers.Singleton(
        lambda client: client[_DB_NAME],
        client=motor_client,
    )

    # ------------------------------------------------------------------
    # Factories (Abstract Factory pattern)
    # ------------------------------------------------------------------

    web_crawler_factory: providers.Singleton = providers.Singleton(
        WebCrawlerFactory
    )

    wikipedia_crawler_factory: providers.Singleton = providers.Singleton(
        WikipediaCrawlerFactory
    )

    rss_crawler_factory: providers.Singleton = providers.Singleton(
        RSSCrawlerFactory
    )

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    raw_content_repository: providers.Singleton = providers.Singleton(
        RawContentRepository,
        db=motor_db,
    )

    filtered_content_repository: providers.Singleton = providers.Singleton(
        FilteredContentRepository,
        db=motor_db,
    )

    podcast_status_repository: providers.Singleton = providers.Singleton(
        PodcastStatusRepository,
        db=motor_db,
    )

    # ------------------------------------------------------------------
    # Filter strategies & pipeline
    # ------------------------------------------------------------------

    quality_filter: providers.Singleton = providers.Singleton(QualityFilter)

    deduplication_filter: providers.Singleton = providers.Singleton(
        DeduplicationFilter
    )

    # RelevanceFilter is topic-dependent; provide a factory so callers can
    # create topic-specific instances.
    relevance_filter_factory: providers.Factory = providers.Factory(
        RelevanceFilter,
        topic="",  # overridden by callers via .override() or direct instantiation
    )

    # Default pipeline uses a placeholder RelevanceFilter("").
    # The orchestrator rebuilds the pipeline with the live topic at runtime.
    filter_pipeline: providers.Singleton = providers.Singleton(
        FilterPipeline,
        strategies=providers.List(
            quality_filter,
            deduplication_filter,
            providers.Factory(RelevanceFilter, topic=""),
        ),
    )

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    orchestrator: providers.Singleton = providers.Singleton(
        CrawlerOrchestrator,
        web_factory=web_crawler_factory,
        wikipedia_factory=wikipedia_crawler_factory,
        rss_factory=rss_crawler_factory,
        raw_repo=raw_content_repository,
        filtered_repo=filtered_content_repository,
        quality_filter=quality_filter,
        dedup_filter=deduplication_filter,
        producer=kafka_producer,
        podcast_status_repo=podcast_status_repository,
    )

    # ------------------------------------------------------------------
    # Kafka consumer
    # ------------------------------------------------------------------

    kafka_consumer: providers.Singleton = providers.Singleton(
        KafkaConsumer,
        orchestrator=orchestrator,
        broker=_KAFKA_BROKER,
    )
