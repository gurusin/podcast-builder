"""RawContentRepository — persists raw (unfiltered) chunks to MongoDB.

Collection: ``raw_content``

Document schema
---------------
.. code-block:: python

    {
        "podcastId": str,
        "chunks": [{"url": str, "title": str, "content": str}],
        "createdAt": datetime,
    }
"""
from datetime import datetime, timezone

from pymongo.asynchronous.database import AsyncDatabase

from .base import BaseContentRepository


class RawContentRepository(BaseContentRepository):
    """Saves and retrieves raw content chunks from the ``raw_content`` collection.

    Parameters
    ----------
    db:
        An async Motor database instance injected by the DI container.
    """

    _COLLECTION = "raw_content"

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db[self._COLLECTION]

    async def save(self, podcast_id: str, chunks: list[dict]) -> None:
        """Insert a new raw-content document for *podcast_id*.

        Parameters
        ----------
        podcast_id:
            UUID string of the podcast episode.
        chunks:
            Raw crawler output chunks.
        """
        document = {
            "podcastId": podcast_id,
            "chunks": chunks,
            "createdAt": datetime.now(tz=timezone.utc),
        }
        await self._collection.insert_one(document)

    async def find_by_podcast_id(self, podcast_id: str) -> dict | None:
        """Return the raw-content document for *podcast_id*, or ``None``.

        Parameters
        ----------
        podcast_id:
            UUID string of the podcast episode.
        """
        return await self._collection.find_one({"podcastId": podcast_id})
