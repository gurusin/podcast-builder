"""FilteredContentRepository — persists scored, filtered chunks to MongoDB.

Collection: ``filtered_content``

Document schema
---------------
.. code-block:: python

    {
        "podcastId": str,
        "chunks": [{"url": str, "title": str, "content": str, "score": float}],
        "createdAt": datetime,
    }
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from .base import BaseContentRepository


class FilteredContentRepository(BaseContentRepository):
    """Saves and retrieves filtered content chunks from ``filtered_content``.

    Parameters
    ----------
    db:
        An async Motor database instance injected by the DI container.
    """

    _COLLECTION = "filtered_content"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[self._COLLECTION]

    async def save(self, podcast_id: str, chunks: list[dict]) -> None:
        """Insert a new filtered-content document for *podcast_id*.

        Parameters
        ----------
        podcast_id:
            UUID string of the podcast episode.
        chunks:
            Filtered, scored chunks (each carries a ``"score"`` key).
        """
        document = {
            "podcastId": podcast_id,
            "chunks": chunks,
            "createdAt": datetime.now(tz=timezone.utc),
        }
        await self._collection.insert_one(document)

    async def find_by_podcast_id(self, podcast_id: str) -> dict | None:
        """Return the filtered-content document for *podcast_id*, or ``None``.

        Parameters
        ----------
        podcast_id:
            UUID string of the podcast episode.
        """
        return await self._collection.find_one({"podcastId": podcast_id})
