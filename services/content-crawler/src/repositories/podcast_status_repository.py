"""PodcastStatusRepository — updates podcast status in the shared podcasts collection."""

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_COLLECTION = "podcasts"


class PodcastStatusRepository:
    """Writes status updates to the `podcasts` collection owned by Request Processor.

    The content crawler only ever transitions a podcast to CRAWLING, never to
    terminal states — those are the Generator's responsibility.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[_COLLECTION]

    async def set_crawling(self, podcast_id: str) -> None:
        await self._col.update_one(
            {"podcastId": podcast_id},
            {"$set": {"status": "CRAWLING", "updatedAt": datetime.now(tz=timezone.utc)}},
        )
        logger.debug("PodcastStatusRepository: set CRAWLING for podcastId=%s", podcast_id)
