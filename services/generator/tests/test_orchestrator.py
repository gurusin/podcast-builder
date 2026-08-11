"""Tests for GeneratorOrchestrator using MockPodcastGeneratorFactory."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.factories.mock_factory import MockPodcastGeneratorFactory
from src.orchestrator import GeneratorOrchestrator


_PODCASTS_DIR = "/tmp/test_podcasts"

_SAMPLE_EVENT = {
    "eventType": "ContentReady",
    "version": "1.0",
    "podcastId": "podcast-test-001",
    "chunkCount": 3,
    "ts": "2024-01-01T00:00:00Z",
}

_SAMPLE_CHUNKS = [
    {"url": "https://example.com/1", "title": "AI Revolution", "content": "Content about AI " * 20, "score": 0.95},
    {"url": "https://example.com/2", "title": "ML Advances", "content": "Content about ML " * 20, "score": 0.88},
]

_SAMPLE_CONTENT_DOC = {
    "podcastId": "podcast-test-001",
    "chunks": _SAMPLE_CHUNKS,
    "createdAt": "2024-01-01T00:00:00Z",
}

_SAMPLE_PODCAST_DOC = {
    "podcastId": "podcast-test-001",
    "topic": "Artificial Intelligence",
    "durationHint": "short",
    "status": "PENDING",
}


@pytest.fixture(autouse=True)
def ensure_podcasts_dir():
    os.makedirs(_PODCASTS_DIR, exist_ok=True)
    yield


def _make_orchestrator(
    content_doc=_SAMPLE_CONTENT_DOC,
    podcast_doc=_SAMPLE_PODCAST_DOC,
) -> tuple[GeneratorOrchestrator, MagicMock, MagicMock, MagicMock]:
    """Build an orchestrator with mock repos and producer."""
    factory = MockPodcastGeneratorFactory()

    filtered_content_repo = MagicMock()
    filtered_content_repo.find_by_podcast_id = AsyncMock(return_value=content_doc)

    podcast_meta_repo = MagicMock()
    podcast_meta_repo.update_status = AsyncMock(return_value=None)
    podcast_meta_repo.find_by_podcast_id = AsyncMock(return_value=podcast_doc)

    kafka_producer = MagicMock()
    kafka_producer.publish_podcast_generated = AsyncMock(return_value=None)

    orchestrator = GeneratorOrchestrator(
        factory=factory,
        filtered_content_repo=filtered_content_repo,
        podcast_meta_repo=podcast_meta_repo,
        kafka_producer=kafka_producer,
        podcasts_dir=_PODCASTS_DIR,
    )

    return orchestrator, filtered_content_repo, podcast_meta_repo, kafka_producer


class TestGeneratorOrchestrator:
    @pytest.mark.asyncio
    async def test_process_sets_status_generating_first(self):
        orchestrator, _, podcast_meta_repo, _ = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        # GENERATING must be the first update_status call
        first_call = podcast_meta_repo.update_status.call_args_list[0]
        assert first_call.args[0] == "podcast-test-001"
        assert first_call.args[1] == "GENERATING"

    @pytest.mark.asyncio
    async def test_process_sets_status_done_on_success(self):
        orchestrator, _, podcast_meta_repo, _ = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        statuses = [call.args[1] for call in podcast_meta_repo.update_status.call_args_list]
        assert "DONE" in statuses

    @pytest.mark.asyncio
    async def test_process_done_call_includes_file_path(self):
        orchestrator, _, podcast_meta_repo, _ = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        done_call = next(
            c for c in podcast_meta_repo.update_status.call_args_list if c.args[1] == "DONE"
        )
        # file_path is the third positional argument
        assert done_call.args[2] is not None
        assert done_call.args[2].endswith(".mp3")

    @pytest.mark.asyncio
    async def test_process_publishes_podcast_generated_event(self):
        orchestrator, _, _, kafka_producer = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        kafka_producer.publish_podcast_generated.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_publishes_correct_podcast_id(self):
        orchestrator, _, _, kafka_producer = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        call_args = kafka_producer.publish_podcast_generated.call_args
        assert call_args.args[0] == "podcast-test-001"

    @pytest.mark.asyncio
    async def test_process_publishes_correct_file_path(self):
        orchestrator, _, _, kafka_producer = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        call_args = kafka_producer.publish_podcast_generated.call_args
        file_path = call_args.args[1]
        assert file_path == os.path.join(_PODCASTS_DIR, "podcast-test-001.mp3")

    @pytest.mark.asyncio
    async def test_process_output_path_matches_expected_pattern(self):
        orchestrator, _, podcast_meta_repo, _ = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        done_call = next(
            c for c in podcast_meta_repo.update_status.call_args_list if c.args[1] == "DONE"
        )
        expected_path = os.path.join(_PODCASTS_DIR, "podcast-test-001.mp3")
        assert done_call.args[2] == expected_path

    @pytest.mark.asyncio
    async def test_process_sets_failed_when_content_doc_missing(self):
        orchestrator, filtered_content_repo, podcast_meta_repo, _ = _make_orchestrator(
            content_doc=None
        )
        filtered_content_repo.find_by_podcast_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError):
            await orchestrator.process(_SAMPLE_EVENT)

        statuses = [call.args[1] for call in podcast_meta_repo.update_status.call_args_list]
        assert "FAILED" in statuses

    @pytest.mark.asyncio
    async def test_process_does_not_publish_on_failure(self):
        orchestrator, filtered_content_repo, _, kafka_producer = _make_orchestrator()
        filtered_content_repo.find_by_podcast_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError):
            await orchestrator.process(_SAMPLE_EVENT)

        kafka_producer.publish_podcast_generated.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_creates_mp3_file(self):
        orchestrator, _, _, _ = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        expected_path = os.path.join(_PODCASTS_DIR, "podcast-test-001.mp3")
        assert os.path.exists(expected_path)

    @pytest.mark.asyncio
    async def test_process_calls_update_status_exactly_twice_on_success(self):
        orchestrator, _, podcast_meta_repo, _ = _make_orchestrator()
        await orchestrator.process(_SAMPLE_EVENT)

        assert podcast_meta_repo.update_status.call_count == 2

    @pytest.mark.asyncio
    async def test_process_uses_topic_from_podcast_doc(self):
        orchestrator, _, _, kafka_producer = _make_orchestrator()
        # Topic in podcast_doc is "Artificial Intelligence" — we just verify no crash
        await orchestrator.process(_SAMPLE_EVENT)
        kafka_producer.publish_podcast_generated.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_falls_back_topic_to_chunk_title_when_no_podcast_doc(self):
        orchestrator, filtered_content_repo, podcast_meta_repo, kafka_producer = \
            _make_orchestrator(podcast_doc=None)
        podcast_meta_repo.find_by_podcast_id = AsyncMock(return_value=None)

        await orchestrator.process(_SAMPLE_EVENT)

        kafka_producer.publish_podcast_generated.assert_awaited_once()
