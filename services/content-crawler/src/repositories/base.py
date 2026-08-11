"""BaseContentRepository — abstract repository interface (Repository pattern).

Repositories encapsulate all MongoDB interactions so that the orchestrator
and other business-logic components never import Motor directly.  Swapping
the storage backend (e.g. to an in-memory store for tests) requires only a
new concrete repository class.
"""
from abc import ABC, abstractmethod


class BaseContentRepository(ABC):
    """Abstract base for content persistence repositories.

    Two concrete implementations exist:
    * :class:`~src.repositories.raw_content_repository.RawContentRepository`
      — persists raw (unfiltered) chunks to ``raw_content``.
    * :class:`~src.repositories.filtered_content_repository.FilteredContentRepository`
      — persists scored, filtered chunks to ``filtered_content``.
    """

    @abstractmethod
    async def save(self, podcast_id: str, chunks: list[dict]) -> None:
        """Persist *chunks* for *podcast_id*.

        Parameters
        ----------
        podcast_id:
            UUID string identifying the podcast episode.
        chunks:
            List of chunk dicts to store.
        """

    @abstractmethod
    async def find_by_podcast_id(self, podcast_id: str) -> dict | None:
        """Retrieve the stored document for *podcast_id*.

        Parameters
        ----------
        podcast_id:
            UUID string identifying the podcast episode.

        Returns
        -------
        dict | None
            The stored MongoDB document, or ``None`` if not found.
        """
