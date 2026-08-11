"""Abstract base classes for repositories (Repository pattern)."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseFilteredContentRepository(ABC):
    """Read access to the filtered_content MongoDB collection."""

    @abstractmethod
    async def find_by_podcast_id(self, podcast_id: str) -> Optional[dict]:
        """
        Return the filtered_content document for *podcast_id*, or None.

        Args:
            podcast_id: The UUID string of the podcast.

        Returns:
            Document dict with keys podcastId, chunks, createdAt, or None.
        """


class BasePodcastMetaRepository(ABC):
    """Read/write access to the podcasts MongoDB collection."""

    @abstractmethod
    async def find_by_podcast_id(self, podcast_id: str) -> Optional[dict]:
        """
        Return the podcasts document for *podcast_id*, or None.

        Args:
            podcast_id: The UUID string of the podcast.

        Returns:
            Document dict, or None.
        """

    @abstractmethod
    async def update_status(
        self,
        podcast_id: str,
        status: str,
        file_path: Optional[str] = None,
    ) -> None:
        """
        Update the status (and optionally filePath) of a podcast document.

        Args:
            podcast_id: The UUID string of the podcast.
            status: New status string (e.g. 'GENERATING', 'DONE', 'FAILED').
            file_path: If provided, also sets filePath on the document.
        """
