"""Abstract Factory pattern — ContentSourceFactory.

Design
------
``ContentSourceFactory`` is the *abstract factory* interface.  Each
concrete factory encapsulates the creation of one ``BaseCrawler`` family
member so that the orchestrator never depends on crawler implementation
details.

Factories
---------
* ``WebCrawlerFactory``       → creates a :class:`~src.crawlers.web_crawler.WebCrawler`
* ``WikipediaCrawlerFactory`` → creates a :class:`~src.crawlers.wikipedia_crawler.WikipediaCrawler`
* ``RSSCrawlerFactory``       → creates a :class:`~src.crawlers.rss_crawler.RSSCrawler`

GoF motivation: swapping a crawler implementation requires changing only
the concrete factory, leaving the orchestrator and tests untouched.
"""
from abc import ABC, abstractmethod

from src.crawlers.base import BaseCrawler
from src.crawlers.rss_crawler import RSSCrawler
from src.crawlers.web_crawler import WebCrawler
from src.crawlers.wikipedia_crawler import WikipediaCrawler


class ContentSourceFactory(ABC):
    """Abstract factory — declares the interface for creating crawlers."""

    @abstractmethod
    def create_crawler(self) -> BaseCrawler:
        """Instantiate and return a concrete :class:`BaseCrawler`."""


# ---------------------------------------------------------------------------
# Concrete factories
# ---------------------------------------------------------------------------


class WebCrawlerFactory(ContentSourceFactory):
    """Concrete factory that produces :class:`WebCrawler` instances."""

    def create_crawler(self) -> BaseCrawler:
        return WebCrawler()


class WikipediaCrawlerFactory(ContentSourceFactory):
    """Concrete factory that produces :class:`WikipediaCrawler` instances."""

    def create_crawler(self) -> BaseCrawler:
        return WikipediaCrawler()


class RSSCrawlerFactory(ContentSourceFactory):
    """Concrete factory that produces :class:`RSSCrawler` instances."""

    def create_crawler(self) -> BaseCrawler:
        return RSSCrawler()
