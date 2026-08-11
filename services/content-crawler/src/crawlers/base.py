"""Base crawler abstract class (ABC).

All concrete crawlers must implement `crawl(topic) -> list[dict]` where
every returned dict has exactly the keys: url, title, content.
"""
from abc import ABC, abstractmethod


class BaseCrawler(ABC):
    """Abstract base class for all content crawlers.

    Each concrete crawler is responsible for fetching raw content chunks
    from a specific source type (web, Wikipedia, RSS, …).

    Contract
    --------
    * ``crawl`` must be a coroutine (``async def``).
    * The returned list items must each carry ``url``, ``title``, and
      ``content`` string keys.
    * Network failures must be caught internally; return ``[]`` and log
      the error — never propagate exceptions to callers.
    """

    @abstractmethod
    async def crawl(self, topic: str) -> list[dict]:
        """Fetch content chunks for *topic* and return them.

        Parameters
        ----------
        topic:
            The subject to search for / crawl about.

        Returns
        -------
        list[dict]
            Each element is ``{"url": str, "title": str, "content": str}``.
        """
