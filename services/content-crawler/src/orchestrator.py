"""CrawlerOrchestrator — coordinates crawling, filtering, and publishing.

Sequence for each ``TopicRequested`` event:

1. Instantiate all three crawlers via their injected factories.
2. Crawl all three sources in parallel (``asyncio.gather``).
3. Merge all chunks into ``raw_chunks``.
4. Save ``raw_chunks`` → :class:`~src.repositories.raw_content_repository.RawContentRepository`.
5. Run :class:`~src.filters.filter_pipeline.FilterPipeline` on ``raw_chunks``.
6. Save ``filtered_chunks`` → :class:`~src.repositories.filtered_content_repository.FilteredContentRepository`.
7. Publish a ``ContentReady`` event via :class:`~src.events.kafka_producer.KafkaProducer`.

Each step is awaited sequentially except step 2 (parallel crawling).
Any exception that escapes a crawler is already handled inside the crawler
itself (returns ``[]``), so the orchestrator always completes.
"""
import asyncio
import logging
from datetime import datetime, timezone

from src.events.kafka_producer import KafkaProducer
from src.factories.content_source_factory import ContentSourceFactory
from src.filters.deduplication_filter import DeduplicationFilter
from src.filters.filter_pipeline import FilterPipeline
from src.filters.quality_filter import QualityFilter
from src.filters.relevance_filter import RelevanceFilter
from src.repositories.base import BaseContentRepository
from src.repositories.podcast_status_repository import PodcastStatusRepository

logger = logging.getLogger(__name__)

_TOPIC_CONTENT_READY = "content-ready"


class CrawlerOrchestrator:
    """Orchestrates the end-to-end content-crawling pipeline.

    Parameters
    ----------
    web_factory:
        Factory for creating :class:`~src.crawlers.web_crawler.WebCrawler`.
    wikipedia_factory:
        Factory for creating :class:`~src.crawlers.wikipedia_crawler.WikipediaCrawler`.
    rss_factory:
        Factory for creating :class:`~src.crawlers.rss_crawler.RSSCrawler`.
    raw_repo:
        Repository for raw chunks.
    filtered_repo:
        Repository for filtered chunks.
    filter_pipeline:
        Composed filter pipeline.
    producer:
        Kafka producer for the ``content-ready`` topic.
    """

    def __init__(
        self,
        web_factory: ContentSourceFactory,
        wikipedia_factory: ContentSourceFactory,
        rss_factory: ContentSourceFactory,
        raw_repo: BaseContentRepository,
        filtered_repo: BaseContentRepository,
        quality_filter: QualityFilter,
        dedup_filter: DeduplicationFilter,
        producer: KafkaProducer,
        podcast_status_repo: PodcastStatusRepository,
    ) -> None:
        self._web_factory = web_factory
        self._wikipedia_factory = wikipedia_factory
        self._rss_factory = rss_factory
        self._raw_repo = raw_repo
        self._filtered_repo = filtered_repo
        self._quality_filter = quality_filter
        self._dedup_filter = dedup_filter
        self._producer = producer
        self._podcast_status_repo = podcast_status_repo

    async def process(self, event: dict) -> None:
        """Handle a single ``TopicRequested`` event end-to-end.

        Parameters
        ----------
        event:
            Deserialised Kafka message payload with at minimum ``podcastId``
            and ``topic`` keys.
        """
        podcast_id: str = event["podcastId"]
        topic: str = event["topic"]

        logger.info(
            "Processing TopicRequested — podcastId=%r topic=%r",
            podcast_id,
            topic,
        )

        # 1. Mark as CRAWLING so the read model reflects the current pipeline stage
        await self._podcast_status_repo.set_crawling(podcast_id)

        # 2. Create crawlers via factories
        web_crawler = self._web_factory.create_crawler()
        wiki_crawler = self._wikipedia_factory.create_crawler()
        rss_crawler = self._rss_factory.create_crawler()

        # 3. Crawl in parallel
        results = await asyncio.gather(
            web_crawler.crawl(topic),
            wiki_crawler.crawl(topic),
            rss_crawler.crawl(topic),
            return_exceptions=False,
        )

        # 3. Merge chunks
        raw_chunks: list[dict] = []
        for chunk_list in results:
            raw_chunks.extend(chunk_list)

        logger.info(
            "Crawled %d raw chunks for podcastId=%r",
            len(raw_chunks),
            podcast_id,
        )

        # 4. Persist raw chunks
        await self._raw_repo.save(podcast_id, raw_chunks)

        # 5. Filter — primary sources (Wikipedia main article) always pass through;
        # secondary sources run through quality + dedup + relevance scoring.
        primary_chunks: list[dict] = []
        secondary_chunks: list[dict] = []
        for chunk in raw_chunks:
            if chunk.pop("_primary", False):
                primary_chunks.append(chunk)
            else:
                secondary_chunks.append(chunk)

        topic_pipeline = FilterPipeline(strategies=[
            self._quality_filter,
            self._dedup_filter,
            RelevanceFilter(topic),
        ])
        filtered_secondary = topic_pipeline.run(secondary_chunks)
        # Merge then deduplicate across primary + secondary so duplicate
        # content (e.g. Wikipedia abstract repeated by DuckDuckGo) is removed.
        merged = primary_chunks + filtered_secondary
        filtered_chunks = self._dedup_filter.filter(merged)

        logger.info(
            "Filtered to %d chunks for podcastId=%r",
            len(filtered_chunks),
            podcast_id,
        )

        # 6. Persist filtered chunks
        await self._filtered_repo.save(podcast_id, filtered_chunks)

        # 7. Publish ContentReady event
        content_ready_event = {
            "eventType": "ContentReady",
            "version": "1.0",
            "podcastId": podcast_id,
            "chunkCount": len(filtered_chunks),
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }
        await self._producer.publish(_TOPIC_CONTENT_READY, content_ready_event)

        logger.info(
            "Published ContentReady for podcastId=%r with %d chunks",
            podcast_id,
            len(filtered_chunks),
        )
