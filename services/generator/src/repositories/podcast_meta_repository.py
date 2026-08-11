"""Concrete repository for the podcasts MongoDB collection."""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.repositories.base import BasePodcastMetaRepository

logger = logging.getLogger(__name__)

_COLLECTION = "podcasts"


class PodcastMetaRepository(BasePodcastMetaRepository):
    """Reads and updates podcast metadata documents in MongoDB."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[_COLLECTION]

    async def find_by_podcast_id(self, podcast_id: str) -> Optional[dict]:
        """
        Return the podcasts document for *podcast_id*, or None.

        Args:
            podcast_id: The UUID string identifying the podcast.

        Returns:
            Document dict or None if not found.
        """
        logger.debug("PodcastMetaRepository: querying for podcastId=%s", podcast_id)
        doc = await self._col.find_one({"podcastId": podcast_id})
        return doc

    async def update_status(
        self,
        podcast_id: str,
        status: str,
        file_path: Optional[str] = None,
    ) -> None:
        """
        Set status (and optionally filePath) on the podcasts document.

        Args:
            podcast_id: The UUID string of the podcast.
            status: New status value.
            file_path: When provided, also sets filePath in the document.
        """
        fields: dict = {"status": status}
        if file_path is not None:
            fields["filePath"] = file_path

        logger.debug(
            "PodcastMetaRepository: update_status podcastId=%s status=%s",
            podcast_id,
            status,
        )
        await self._col.update_one(
            {"podcastId": podcast_id},
            {"$set": fields},
        )
