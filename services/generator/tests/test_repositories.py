"""Tests for MongoDB repository implementations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.repositories.filtered_content_repository import FilteredContentRepository
from src.repositories.podcast_meta_repository import PodcastMetaRepository


def _make_db(collection_mock: MagicMock) -> MagicMock:
    """Return a mock AsyncIOMotorDatabase whose __getitem__ returns collection_mock."""
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection_mock)
    return db


class TestFilteredContentRepository:
    def test_find_by_podcast_id_calls_find_one_with_correct_filter(self):
        podcast_id = "test-podcast-123"
        expected_doc = {"podcastId": podcast_id, "chunks": [], "createdAt": "2024-01-01"}

        col = MagicMock()
        col.find_one = AsyncMock(return_value=expected_doc)
        db = _make_db(col)

        repo = FilteredContentRepository(db=db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            repo.find_by_podcast_id(podcast_id)
        )

        col.find_one.assert_awaited_once_with({"podcastId": podcast_id})
        assert result == expected_doc

    def test_find_by_podcast_id_returns_none_when_not_found(self):
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        db = _make_db(col)

        repo = FilteredContentRepository(db=db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            repo.find_by_podcast_id("missing-id")
        )

        assert result is None

    def test_find_by_podcast_id_passes_exact_id(self):
        podcast_id = "unique-uuid-xyz"
        col = MagicMock()
        col.find_one = AsyncMock(return_value={"podcastId": podcast_id})
        db = _make_db(col)

        repo = FilteredContentRepository(db=db)
        import asyncio
        asyncio.get_event_loop().run_until_complete(repo.find_by_podcast_id(podcast_id))

        call_args = col.find_one.call_args
        assert call_args[0][0] == {"podcastId": podcast_id}


class TestPodcastMetaRepository:
    def test_update_status_done_sets_status_and_file_path(self):
        podcast_id = "podcast-abc"
        file_path = "/app/podcasts/podcast-abc.mp3"

        col = MagicMock()
        col.update_one = AsyncMock(return_value=MagicMock())
        db = _make_db(col)

        repo = PodcastMetaRepository(db=db)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            repo.update_status(podcast_id, "DONE", file_path)
        )

        col.update_one.assert_awaited_once_with(
            {"podcastId": podcast_id},
            {"$set": {"status": "DONE", "filePath": file_path}},
        )

    def test_update_status_failed_sets_only_status(self):
        podcast_id = "podcast-xyz"

        col = MagicMock()
        col.update_one = AsyncMock(return_value=MagicMock())
        db = _make_db(col)

        repo = PodcastMetaRepository(db=db)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            repo.update_status(podcast_id, "FAILED")
        )

        call_kwargs = col.update_one.call_args[0][1]
        assert call_kwargs["$set"]["status"] == "FAILED"
        assert "filePath" not in call_kwargs["$set"]

    def test_update_status_failed_does_not_include_file_path_key(self):
        col = MagicMock()
        col.update_one = AsyncMock(return_value=MagicMock())
        db = _make_db(col)

        repo = PodcastMetaRepository(db=db)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            repo.update_status("pod-1", "FAILED")
        )

        set_doc = col.update_one.call_args[0][1]["$set"]
        assert "filePath" not in set_doc

    def test_update_status_generating_sets_only_status(self):
        col = MagicMock()
        col.update_one = AsyncMock(return_value=MagicMock())
        db = _make_db(col)

        repo = PodcastMetaRepository(db=db)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            repo.update_status("pod-1", "GENERATING")
        )

        set_doc = col.update_one.call_args[0][1]["$set"]
        assert set_doc == {"status": "GENERATING"}

    def test_find_by_podcast_id_returns_document(self):
        podcast_id = "podcast-find-me"
        expected = {"podcastId": podcast_id, "status": "PENDING", "topic": "Tech"}

        col = MagicMock()
        col.find_one = AsyncMock(return_value=expected)
        db = _make_db(col)

        repo = PodcastMetaRepository(db=db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            repo.find_by_podcast_id(podcast_id)
        )

        col.find_one.assert_awaited_once_with({"podcastId": podcast_id})
        assert result == expected

    def test_find_by_podcast_id_returns_none_when_missing(self):
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        db = _make_db(col)

        repo = PodcastMetaRepository(db=db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            repo.find_by_podcast_id("nope")
        )

        assert result is None
