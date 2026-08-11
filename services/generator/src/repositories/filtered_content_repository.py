"""Concrete repository for the filtered_content MongoDB collection."""

import logging
from typing import Optional

from pymongo.asynchronous.database import AsyncDatabase

from src.repositories.base import BaseFilteredContentRepository

logger = logging.getLogger(__name__)

_COLLECTION = "filtered_content"


class FilteredContentRepository(BaseFilteredContentRepository):
    """Reads filtered content documents from MongoDB."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._col = db[_COLLECTION]

    async def find_by_podcast_id(self, podcast_id: str) -> Optional[dict]:
        """
        Return the filtered_content document for *podcast_id*, or None.

        Args:
            podcast_id: The UUID string identifying the podcast.

        Returns:
            Document dict or None if not found.
        """
        logger.debug("FilteredContentRepository: querying for podcastId=%s", podcast_id)
        doc = await self._col.find_one({"podcastId": podcast_id})
        return doc
