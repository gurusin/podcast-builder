"""Tests for the concrete crawler implementations.

Each crawler is tested in isolation by mocking the external HTTP/feedparser
calls so the suite runs entirely offline.  Tests verify that:

* The crawler returns a list of dicts with the mandated keys.
* The ``content`` field contains the text that was returned by the mock.
* Network errors are swallowed and an empty list is returned.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.crawlers.rss_crawler import RSSCrawler
from src.crawlers.web_crawler import WebCrawler
from src.crawlers.wikipedia_crawler import WikipediaCrawler


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_httpx_response(payload: dict | bytes, status_code: int = 200):
    """Return a MagicMock that quacks like an httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    if isinstance(payload, bytes):
        mock.content = payload
        mock.json.side_effect = ValueError("not JSON")
    else:
        mock.json.return_value = payload
        mock.content = json.dumps(payload).encode()
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# WikipediaCrawler
# ---------------------------------------------------------------------------

class TestWikipediaCrawler:
    """Tests for :class:`~src.crawlers.wikipedia_crawler.WikipediaCrawler`."""

    @pytest.mark.asyncio
    async def test_crawl_returns_extract_from_summary(self):
        """crawl() includes the ``extract`` text from the summary endpoint."""
        extract_text = "Python is a high-level programming language."
        summary_payload = {
            "extract": extract_text,
            "title": "Python (programming language)",
            "content_urls": {
                "desktop": {"page": "https://en.wikipedia.org/wiki/Python"}
            },
        }
        related_payload = {"pages": []}

        mock_response_summary = _make_httpx_response(summary_payload)
        mock_response_related = _make_httpx_response(related_payload)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            side_effect=[mock_response_summary, mock_response_related]
        )

        with patch("src.crawlers.wikipedia_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WikipediaCrawler()
            chunks = await crawler.crawl("Python")

        assert len(chunks) >= 1
        assert any(extract_text in chunk["content"] for chunk in chunks)

    @pytest.mark.asyncio
    async def test_crawl_includes_related_pages(self):
        """crawl() appends chunks for each related page that has an extract."""
        summary_payload = {
            "extract": "Python is a programming language.",
            "title": "Python",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Python"}},
        }
        related_payload = {
            "pages": [
                {
                    "extract": "Guido van Rossum created Python.",
                    "title": "Guido van Rossum",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Guido"}},
                },
                {
                    "extract": "CPython is the reference implementation.",
                    "title": "CPython",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/CPython"}},
                },
            ]
        }

        mock_summary = _make_httpx_response(summary_payload)
        mock_related = _make_httpx_response(related_payload)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[mock_summary, mock_related])

        with patch("src.crawlers.wikipedia_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WikipediaCrawler()
            chunks = await crawler.crawl("Python")

        # 1 summary + 2 related
        assert len(chunks) == 3
        titles = [c["title"] for c in chunks]
        assert "Guido van Rossum" in titles
        assert "CPython" in titles

    @pytest.mark.asyncio
    async def test_crawl_returns_empty_list_on_http_error(self):
        """crawl() returns [] when the HTTP call raises an exception."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("src.crawlers.wikipedia_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WikipediaCrawler()
            chunks = await crawler.crawl("Python")

        assert chunks == []

    @pytest.mark.asyncio
    async def test_chunk_keys_are_correct(self):
        """Every returned chunk has url, title, and content keys."""
        summary_payload = {
            "extract": "Python is versatile.",
            "title": "Python",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Python"}},
        }
        related_payload = {"pages": []}

        mock_summary = _make_httpx_response(summary_payload)
        mock_related = _make_httpx_response(related_payload)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[mock_summary, mock_related])

        with patch("src.crawlers.wikipedia_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WikipediaCrawler()
            chunks = await crawler.crawl("Python")

        for chunk in chunks:
            assert "url" in chunk
            assert "title" in chunk
            assert "content" in chunk


# ---------------------------------------------------------------------------
# WebCrawler
# ---------------------------------------------------------------------------

class TestWebCrawler:
    """Tests for :class:`~src.crawlers.web_crawler.WebCrawler`."""

    @pytest.mark.asyncio
    async def test_crawl_returns_abstract_text_chunk(self):
        """crawl() returns a chunk for the AbstractText field."""
        payload = {
            "AbstractText": "Some text about Python programming language",
            "AbstractURL": "https://duckduckgo.com/Python",
            "AbstractSource": "Wikipedia",
            "RelatedTopics": [],
        }
        mock_response = _make_httpx_response(payload)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.crawlers.web_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WebCrawler()
            chunks = await crawler.crawl("Python")

        assert len(chunks) >= 1
        assert any("Python" in c["content"] for c in chunks)

    @pytest.mark.asyncio
    async def test_crawl_parses_related_topics(self):
        """crawl() includes chunks for flat RelatedTopics entries."""
        payload = {
            "AbstractText": "",
            "AbstractURL": "",
            "AbstractSource": "",
            "RelatedTopics": [
                {"Text": "related topic one", "FirstURL": "https://ddg.co/1"},
                {"Text": "related topic two", "FirstURL": "https://ddg.co/2"},
            ],
        }
        mock_response = _make_httpx_response(payload)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.crawlers.web_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WebCrawler()
            chunks = await crawler.crawl("Python")

        assert len(chunks) == 2
        contents = [c["content"] for c in chunks]
        assert "related topic one" in contents
        assert "related topic two" in contents

    @pytest.mark.asyncio
    async def test_crawl_parses_nested_related_topics(self):
        """crawl() unpacks grouped RelatedTopics (items with 'Topics' key)."""
        payload = {
            "AbstractText": "",
            "AbstractURL": "",
            "AbstractSource": "",
            "RelatedTopics": [
                {
                    "Topics": [
                        {"Text": "sub topic A", "FirstURL": "https://ddg.co/a"},
                    ]
                }
            ],
        }
        mock_response = _make_httpx_response(payload)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.crawlers.web_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WebCrawler()
            chunks = await crawler.crawl("Python")

        assert any(c["content"] == "sub topic A" for c in chunks)

    @pytest.mark.asyncio
    async def test_crawl_returns_empty_list_on_exception(self):
        """crawl() returns [] when the HTTP call raises."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("src.crawlers.web_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WebCrawler()
            chunks = await crawler.crawl("Python")

        assert chunks == []

    @pytest.mark.asyncio
    async def test_chunk_keys_are_correct(self):
        """Every returned chunk has url, title, and content keys."""
        payload = {
            "AbstractText": "Some abstract text about the topic.",
            "AbstractURL": "https://ddg.co",
            "AbstractSource": "Source",
            "RelatedTopics": [],
        }
        mock_response = _make_httpx_response(payload)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.crawlers.web_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = WebCrawler()
            chunks = await crawler.crawl("topic")

        for chunk in chunks:
            assert "url" in chunk
            assert "title" in chunk
            assert "content" in chunk


# ---------------------------------------------------------------------------
# RSSCrawler
# ---------------------------------------------------------------------------

class TestRSSCrawler:
    """Tests for :class:`~src.crawlers.rss_crawler.RSSCrawler`."""

    def _make_feed(self, entries: list[dict]):
        """Return a MagicMock that mimics a feedparser result object."""
        feed = MagicMock()
        feed.entries = [
            MagicMock(
                **{
                    "get.side_effect": lambda key, default="": e.get(key, default),
                    **e,
                }
            )
            for e in entries
        ]
        # Make each entry support .get() correctly
        parsed_entries = []
        for e in entries:
            entry_mock = MagicMock()
            entry_mock.get = lambda key, default="", _e=e: _e.get(key, default)
            parsed_entries.append(entry_mock)
        feed.entries = parsed_entries
        return feed

    @pytest.mark.asyncio
    async def test_crawl_returns_entries_matching_topic(self):
        """crawl() returns entries whose title or summary contains the topic."""
        rss_entries = [
            {"title": "Python 3.12 Released", "summary": "New version of Python.", "link": "http://bbc.co.uk/1"},
            {"title": "Unrelated news story", "summary": "Nothing to do with the topic.", "link": "http://bbc.co.uk/2"},
            {"title": "Python overtakes Java", "summary": "Python popularity grows.", "link": "http://bbc.co.uk/3"},
        ]
        feed_mock = self._make_feed(rss_entries)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("src.crawlers.rss_crawler.httpx.AsyncClient", return_value=mock_client),
            patch("src.crawlers.rss_crawler.feedparser.parse", return_value=feed_mock),
        ):
            crawler = RSSCrawler()
            chunks = await crawler.crawl("Python")

        assert len(chunks) == 2
        for chunk in chunks:
            assert "Python" in chunk["title"]

    @pytest.mark.asyncio
    async def test_crawl_respects_max_results(self):
        """crawl() returns at most 5 matching entries."""
        rss_entries = [
            {"title": f"Python story {i}", "summary": "Python content.", "link": f"http://bbc.co.uk/{i}"}
            for i in range(10)
        ]
        feed_mock = self._make_feed(rss_entries)

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("src.crawlers.rss_crawler.httpx.AsyncClient", return_value=mock_client),
            patch("src.crawlers.rss_crawler.feedparser.parse", return_value=feed_mock),
        ):
            crawler = RSSCrawler()
            chunks = await crawler.crawl("Python")

        assert len(chunks) <= 5

    @pytest.mark.asyncio
    async def test_crawl_returns_empty_list_on_exception(self):
        """crawl() returns [] when HTTP raises."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("network error"))

        with patch("src.crawlers.rss_crawler.httpx.AsyncClient", return_value=mock_client):
            crawler = RSSCrawler()
            chunks = await crawler.crawl("Python")

        assert chunks == []

    @pytest.mark.asyncio
    async def test_chunk_keys_are_correct(self):
        """Every returned chunk has url, title, and content keys."""
        rss_entries = [
            {"title": "Python news", "summary": "A Python related summary.", "link": "http://bbc.co.uk/py"},
        ]
        feed_mock = self._make_feed(rss_entries)

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("src.crawlers.rss_crawler.httpx.AsyncClient", return_value=mock_client),
            patch("src.crawlers.rss_crawler.feedparser.parse", return_value=feed_mock),
        ):
            crawler = RSSCrawler()
            chunks = await crawler.crawl("Python")

        for chunk in chunks:
            assert "url" in chunk
            assert "title" in chunk
            assert "content" in chunk
