"""Tests for CrawlerOrchestrator.

All external dependencies (factories, repositories, pipeline, producer) are
mocked so the suite is hermetic.  Tests verify the sequencing and contract
of ``CrawlerOrchestrator.process()``.
"""
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.orchestrator import CrawlerOrchestrator


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_EVENT = {
    "eventType": "TopicRequested",
    "version": "1.0",
    "podcastId": "pod-uuid-001",
    "topic": "space exploration",
    "durationHint": "medium",
    "ts": "2024-01-01T00:00:00Z",
}

_LONG_CHUNK = {
    "url": "https://example.com",
    "title": "Space",
    "content": "s" * 300,
}


def _make_factory(chunks: list[dict]):
    """Return a factory mock whose create_crawler() returns a crawler yielding *chunks*."""
    crawler = MagicMock()
    crawler.crawl = AsyncMock(return_value=chunks)
    factory = MagicMock()
    factory.create_crawler = MagicMock(return_value=crawler)
    return factory, crawler


def _make_pipeline(output: list[dict] | None = None):
    """Return a FilterPipeline mock whose run() returns *output*."""
    pipeline = MagicMock()
    pipeline.run = MagicMock(return_value=output if output is not None else [])
    return pipeline


def _make_orchestrator(
    web_chunks=None,
    wiki_chunks=None,
    rss_chunks=None,
    pipeline_output=None,
):
    """Build a fully mocked orchestrator and return it with its mocks."""
    web_factory, web_crawler = _make_factory(web_chunks or [])
    wiki_factory, wiki_crawler = _make_factory(wiki_chunks or [])
    rss_factory, rss_crawler = _make_factory(rss_chunks or [])

    raw_repo = MagicMock()
    raw_repo.save = AsyncMock()
    filtered_repo = MagicMock()
    filtered_repo.save = AsyncMock()

    pipeline = _make_pipeline(pipeline_output)

    producer = MagicMock()
    producer.publish = AsyncMock()

    orchestrator = CrawlerOrchestrator(
        web_factory=web_factory,
        wikipedia_factory=wiki_factory,
        rss_factory=rss_factory,
        raw_repo=raw_repo,
        filtered_repo=filtered_repo,
        filter_pipeline=pipeline,
        producer=producer,
    )

    return orchestrator, {
        "web_factory": web_factory,
        "wiki_factory": wiki_factory,
        "rss_factory": rss_factory,
        "web_crawler": web_crawler,
        "wiki_crawler": wiki_crawler,
        "rss_crawler": rss_crawler,
        "raw_repo": raw_repo,
        "filtered_repo": filtered_repo,
        "pipeline": pipeline,
        "producer": producer,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCrawlerOrchestrator:
    """Tests for :class:`~src.orchestrator.CrawlerOrchestrator`."""

    @pytest.mark.asyncio
    async def test_process_calls_all_factory_create_crawler(self):
        """process() must call create_crawler() on each factory exactly once."""
        orchestrator, mocks = _make_orchestrator()

        await orchestrator.process(SAMPLE_EVENT)

        mocks["web_factory"].create_crawler.assert_called_once()
        mocks["wiki_factory"].create_crawler.assert_called_once()
        mocks["rss_factory"].create_crawler.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_calls_crawl_on_all_crawlers(self):
        """process() must call crawl(topic) on each instantiated crawler."""
        orchestrator, mocks = _make_orchestrator()

        await orchestrator.process(SAMPLE_EVENT)

        topic = SAMPLE_EVENT["topic"]
        mocks["web_crawler"].crawl.assert_awaited_once_with(topic)
        mocks["wiki_crawler"].crawl.assert_awaited_once_with(topic)
        mocks["rss_crawler"].crawl.assert_awaited_once_with(topic)

    @pytest.mark.asyncio
    async def test_process_saves_raw_content_before_filtered(self):
        """raw_repo.save must be called before filtered_repo.save."""
        call_order = []

        web_factory, _ = _make_factory([_LONG_CHUNK])
        wiki_factory, _ = _make_factory([])
        rss_factory, _ = _make_factory([])

        raw_repo = MagicMock()
        async def raw_save(pod_id, chunks):
            call_order.append("raw")
        raw_repo.save = raw_save

        filtered_repo = MagicMock()
        async def filtered_save(pod_id, chunks):
            call_order.append("filtered")
        filtered_repo.save = filtered_save

        pipeline = _make_pipeline([_LONG_CHUNK])
        producer = MagicMock()
        producer.publish = AsyncMock()

        orchestrator = CrawlerOrchestrator(
            web_factory=web_factory,
            wikipedia_factory=wiki_factory,
            rss_factory=rss_factory,
            raw_repo=raw_repo,
            filtered_repo=filtered_repo,
            filter_pipeline=pipeline,
            producer=producer,
        )

        await orchestrator.process(SAMPLE_EVENT)

        assert call_order.index("raw") < call_order.index("filtered"), (
            "raw_repo.save must be called before filtered_repo.save"
        )

    @pytest.mark.asyncio
    async def test_process_saves_filtered_content_before_publish(self):
        """filtered_repo.save must be called before producer.publish."""
        call_order = []

        web_factory, _ = _make_factory([])
        wiki_factory, _ = _make_factory([])
        rss_factory, _ = _make_factory([])

        raw_repo = MagicMock()
        raw_repo.save = AsyncMock()

        filtered_repo = MagicMock()
        async def filtered_save(pod_id, chunks):
            call_order.append("filtered")
        filtered_repo.save = filtered_save

        pipeline = _make_pipeline([])

        producer = MagicMock()
        async def publish(topic, msg):
            call_order.append("publish")
        producer.publish = publish

        orchestrator = CrawlerOrchestrator(
            web_factory=web_factory,
            wikipedia_factory=wiki_factory,
            rss_factory=rss_factory,
            raw_repo=raw_repo,
            filtered_repo=filtered_repo,
            filter_pipeline=pipeline,
            producer=producer,
        )

        await orchestrator.process(SAMPLE_EVENT)

        assert call_order.index("filtered") < call_order.index("publish"), (
            "filtered_repo.save must be called before producer.publish"
        )

    @pytest.mark.asyncio
    async def test_process_publishes_content_ready_event(self):
        """process() must publish a ContentReady event to the content-ready topic."""
        orchestrator, mocks = _make_orchestrator(
            wiki_chunks=[_LONG_CHUNK],
            pipeline_output=[_LONG_CHUNK],
        )

        await orchestrator.process(SAMPLE_EVENT)

        mocks["producer"].publish.assert_awaited_once()
        publish_call = mocks["producer"].publish.call_args
        topic_arg = publish_call[0][0]
        message_arg = publish_call[0][1]

        assert topic_arg == "content-ready"
        assert message_arg["eventType"] == "ContentReady"
        assert message_arg["podcastId"] == SAMPLE_EVENT["podcastId"]
        assert "chunkCount" in message_arg
        assert "ts" in message_arg

    @pytest.mark.asyncio
    async def test_process_content_ready_chunk_count_matches_filtered(self):
        """chunkCount in ContentReady event equals len(filtered_chunks)."""
        filtered = [_LONG_CHUNK, {**_LONG_CHUNK, "url": "https://example.com/2"}]
        orchestrator, mocks = _make_orchestrator(
            web_chunks=filtered,
            pipeline_output=filtered,
        )

        await orchestrator.process(SAMPLE_EVENT)

        message_arg = mocks["producer"].publish.call_args[0][1]
        assert message_arg["chunkCount"] == len(filtered)

    @pytest.mark.asyncio
    async def test_process_with_empty_crawl_results_completes_without_error(self):
        """process() must complete normally even when all crawlers return []."""
        orchestrator, mocks = _make_orchestrator(
            web_chunks=[],
            wiki_chunks=[],
            rss_chunks=[],
            pipeline_output=[],
        )

        # Should not raise
        await orchestrator.process(SAMPLE_EVENT)

        mocks["raw_repo"].save.assert_awaited_once_with(
            SAMPLE_EVENT["podcastId"], []
        )
        mocks["filtered_repo"].save.assert_awaited_once_with(
            SAMPLE_EVENT["podcastId"], []
        )
        mocks["producer"].publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_merges_chunks_from_all_crawlers(self):
        """raw_repo.save receives the merged chunks from all three crawlers."""
        web_chunk = {"url": "w", "title": "web", "content": "web content"}
        wiki_chunk = {"url": "k", "title": "wiki", "content": "wiki content"}
        rss_chunk = {"url": "r", "title": "rss", "content": "rss content"}

        orchestrator, mocks = _make_orchestrator(
            web_chunks=[web_chunk],
            wiki_chunks=[wiki_chunk],
            rss_chunks=[rss_chunk],
            pipeline_output=[],
        )

        await orchestrator.process(SAMPLE_EVENT)

        saved_chunks = mocks["raw_repo"].save.call_args[0][1]
        assert web_chunk in saved_chunks
        assert wiki_chunk in saved_chunks
        assert rss_chunk in saved_chunks
        assert len(saved_chunks) == 3

    @pytest.mark.asyncio
    async def test_process_passes_raw_chunks_to_pipeline(self):
        """FilterPipeline.run() is called with the merged raw chunks."""
        web_chunk = {"url": "w", "title": "web", "content": "web content"}
        orchestrator, mocks = _make_orchestrator(
            web_chunks=[web_chunk],
            pipeline_output=[],
        )

        await orchestrator.process(SAMPLE_EVENT)

        pipeline_input = mocks["pipeline"].run.call_args[0][0]
        assert web_chunk in pipeline_input

    @pytest.mark.asyncio
    async def test_process_event_version_is_1_0(self):
        """The published ContentReady event must carry version '1.0'."""
        orchestrator, mocks = _make_orchestrator()

        await orchestrator.process(SAMPLE_EVENT)

        message_arg = mocks["producer"].publish.call_args[0][1]
        assert message_arg["version"] == "1.0"
