"""Tests for RawContentRepository and FilteredContentRepository.

Motor's AsyncIOMotorClient is mocked so no real MongoDB connection is made.
Tests verify:
  * ``save()`` calls ``insert_one`` with the correct document shape.
  * ``find_by_podcast_id()`` calls ``find_one`` with the correct query.
  * ``createdAt`` is a datetime object in the persisted document.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.repositories.filtered_content_repository import FilteredContentRepository
from src.repositories.raw_content_repository import RawContentRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(collection_name: str):
    """Return a MagicMock database whose collection supports async ops."""
    collection = MagicMock()
    collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
    collection.find_one = AsyncMock(return_value={"podcastId": "pod-1", "chunks": []})

    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


SAMPLE_PODCAST_ID = "550e8400-e29b-41d4-a716-446655440000"
SAMPLE_RAW_CHUNKS = [
    {"url": "https://example.com/1", "title": "Title 1", "content": "Content one"},
    {"url": "https://example.com/2", "title": "Title 2", "content": "Content two"},
]
SAMPLE_FILTERED_CHUNKS = [
    {"url": "https://example.com/1", "title": "Title 1", "content": "Content one", "score": 0.85},
]


# ---------------------------------------------------------------------------
# RawContentRepository
# ---------------------------------------------------------------------------

class TestRawContentRepository:
    """Tests for :class:`~src.repositories.raw_content_repository.RawContentRepository`."""

    @pytest.mark.asyncio
    async def test_save_calls_insert_one(self):
        """save() must call collection.insert_one exactly once."""
        db, collection = _make_mock_db("raw_content")
        repo = RawContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_RAW_CHUNKS)

        collection.insert_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_document_has_podcast_id(self):
        """The document passed to insert_one must contain the correct podcastId."""
        db, collection = _make_mock_db("raw_content")
        repo = RawContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_RAW_CHUNKS)

        call_args = collection.insert_one.call_args[0][0]
        assert call_args["podcastId"] == SAMPLE_PODCAST_ID

    @pytest.mark.asyncio
    async def test_save_document_has_chunks(self):
        """The document passed to insert_one must contain the chunks list."""
        db, collection = _make_mock_db("raw_content")
        repo = RawContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_RAW_CHUNKS)

        call_args = collection.insert_one.call_args[0][0]
        assert call_args["chunks"] == SAMPLE_RAW_CHUNKS

    @pytest.mark.asyncio
    async def test_save_document_has_created_at_datetime(self):
        """The document passed to insert_one must contain a datetime createdAt."""
        db, collection = _make_mock_db("raw_content")
        repo = RawContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_RAW_CHUNKS)

        call_args = collection.insert_one.call_args[0][0]
        assert isinstance(call_args["createdAt"], datetime)

    @pytest.mark.asyncio
    async def test_find_by_podcast_id_calls_find_one(self):
        """find_by_podcast_id() must call find_one with the correct query."""
        db, collection = _make_mock_db("raw_content")
        repo = RawContentRepository(db=db)

        await repo.find_by_podcast_id(SAMPLE_PODCAST_ID)

        collection.find_one.assert_awaited_once_with(
            {"podcastId": SAMPLE_PODCAST_ID}
        )

    @pytest.mark.asyncio
    async def test_find_by_podcast_id_returns_document(self):
        """find_by_podcast_id() returns the value from find_one."""
        db, collection = _make_mock_db("raw_content")
        expected = {"podcastId": SAMPLE_PODCAST_ID, "chunks": SAMPLE_RAW_CHUNKS}
        collection.find_one = AsyncMock(return_value=expected)
        repo = RawContentRepository(db=db)

        result = await repo.find_by_podcast_id(SAMPLE_PODCAST_ID)

        assert result == expected

    @pytest.mark.asyncio
    async def test_find_by_podcast_id_returns_none_when_not_found(self):
        """find_by_podcast_id() returns None when find_one returns None."""
        db, collection = _make_mock_db("raw_content")
        collection.find_one = AsyncMock(return_value=None)
        repo = RawContentRepository(db=db)

        result = await repo.find_by_podcast_id("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_save_uses_raw_content_collection(self):
        """RawContentRepository accesses the raw_content collection."""
        db = MagicMock()
        collection = MagicMock()
        collection.insert_one = AsyncMock()

        # Track which collection name is accessed
        accessed_keys = []

        def getitem(key):
            accessed_keys.append(key)
            return collection

        db.__getitem__ = getitem
        repo = RawContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, [])

        assert "raw_content" in accessed_keys


# ---------------------------------------------------------------------------
# FilteredContentRepository
# ---------------------------------------------------------------------------

class TestFilteredContentRepository:
    """Tests for :class:`~src.repositories.filtered_content_repository.FilteredContentRepository`."""

    @pytest.mark.asyncio
    async def test_save_calls_insert_one(self):
        """save() must call collection.insert_one exactly once."""
        db, collection = _make_mock_db("filtered_content")
        repo = FilteredContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_FILTERED_CHUNKS)

        collection.insert_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_document_has_podcast_id(self):
        """The document passed to insert_one must contain the correct podcastId."""
        db, collection = _make_mock_db("filtered_content")
        repo = FilteredContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_FILTERED_CHUNKS)

        call_args = collection.insert_one.call_args[0][0]
        assert call_args["podcastId"] == SAMPLE_PODCAST_ID

    @pytest.mark.asyncio
    async def test_save_document_has_chunks_with_score(self):
        """Filtered chunks (with score) are persisted verbatim."""
        db, collection = _make_mock_db("filtered_content")
        repo = FilteredContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_FILTERED_CHUNKS)

        call_args = collection.insert_one.call_args[0][0]
        assert call_args["chunks"] == SAMPLE_FILTERED_CHUNKS
        assert call_args["chunks"][0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_save_document_has_created_at_datetime(self):
        """The document must include a datetime createdAt."""
        db, collection = _make_mock_db("filtered_content")
        repo = FilteredContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, SAMPLE_FILTERED_CHUNKS)

        call_args = collection.insert_one.call_args[0][0]
        assert isinstance(call_args["createdAt"], datetime)

    @pytest.mark.asyncio
    async def test_find_by_podcast_id_calls_find_one(self):
        """find_by_podcast_id() must call find_one with the correct query."""
        db, collection = _make_mock_db("filtered_content")
        repo = FilteredContentRepository(db=db)

        await repo.find_by_podcast_id(SAMPLE_PODCAST_ID)

        collection.find_one.assert_awaited_once_with(
            {"podcastId": SAMPLE_PODCAST_ID}
        )

    @pytest.mark.asyncio
    async def test_find_by_podcast_id_returns_document(self):
        """find_by_podcast_id() returns the document from find_one."""
        db, collection = _make_mock_db("filtered_content")
        expected = {"podcastId": SAMPLE_PODCAST_ID, "chunks": SAMPLE_FILTERED_CHUNKS}
        collection.find_one = AsyncMock(return_value=expected)
        repo = FilteredContentRepository(db=db)

        result = await repo.find_by_podcast_id(SAMPLE_PODCAST_ID)

        assert result == expected

    @pytest.mark.asyncio
    async def test_save_uses_filtered_content_collection(self):
        """FilteredContentRepository accesses the filtered_content collection."""
        db = MagicMock()
        collection = MagicMock()
        collection.insert_one = AsyncMock()

        accessed_keys = []

        def getitem(key):
            accessed_keys.append(key)
            return collection

        db.__getitem__ = getitem
        repo = FilteredContentRepository(db=db)

        await repo.save(SAMPLE_PODCAST_ID, [])

        assert "filtered_content" in accessed_keys
