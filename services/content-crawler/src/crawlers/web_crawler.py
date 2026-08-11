"""WebCrawler — fetches content via the DuckDuckGo Instant Answer API.

Endpoint (no API key needed):
  ``https://api.duckduckgo.com/?q={topic}&format=json&no_redirect=1``

When DDG returns a disambiguation page (Type == "D"), RelatedTopics are
one-liner stubs listing albums, films, and books that share the same name.
We skip them and only keep the AbstractText and genuinely informational
topic entries.
"""
import logging
import urllib.parse

import httpx

from .base import BaseCrawler

logger = logging.getLogger(__name__)

_DDG_URL = "https://api.duckduckgo.com/"
_TIMEOUT = 10.0
_HEADERS = {"User-Agent": "podcast-builder/1.0 (https://github.com/gurusin/podcast-builder)"}

# Minimum content length to be considered substantive
_MIN_LENGTH = 150


class WebCrawler(BaseCrawler):
    """Crawls DuckDuckGo Instant Answers for a topic."""

    async def crawl(self, topic: str) -> list[dict]:
        """Return substantive content chunks from DuckDuckGo Instant Answers.

        Parameters
        ----------
        topic:
            Search query.

        Returns
        -------
        list[dict]
            ``[{"url": str, "title": str, "content": str}, ...]``
        """
        chunks: list[dict] = []
        params = {"q": topic, "format": "json", "no_redirect": "1"}

        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
            ) as client:
                resp = await client.get(_DDG_URL, params=params)
                resp.raise_for_status()
                if not resp.content:
                    return chunks
                data = resp.json()

            page_type = data.get("Type", "")  # "A" = article, "D" = disambiguation, "C" = category

            # AbstractText is always useful regardless of page type
            abstract_text = data.get("AbstractText", "").strip()
            abstract_url = data.get("AbstractURL", _DDG_URL)
            abstract_source = data.get("AbstractSource", "DuckDuckGo")
            if abstract_text and len(abstract_text) >= _MIN_LENGTH:
                chunks.append(
                    {
                        "url": abstract_url,
                        "title": f"{abstract_source}: {topic}",
                        "content": abstract_text,
                    }
                )

            # Skip RelatedTopics entirely for disambiguation pages —
            # they are lists of same-named albums/movies/books, not informational content.
            if page_type == "D":
                logger.debug("WebCrawler: DDG returned disambiguation page for %r; skipping RelatedTopics", topic)
                return chunks

            # For non-disambiguation pages, include substantive RelatedTopics
            for item in data.get("RelatedTopics", []):
                if "Topics" in item:
                    for sub in item["Topics"]:
                        text = sub.get("Text", "").strip()
                        if len(text) >= _MIN_LENGTH:
                            chunks.append(
                                {
                                    "url": sub.get("FirstURL", _DDG_URL),
                                    "title": topic,
                                    "content": text,
                                }
                            )
                else:
                    text = item.get("Text", "").strip()
                    if len(text) >= _MIN_LENGTH:
                        chunks.append(
                            {
                                "url": item.get("FirstURL", _DDG_URL),
                                "title": topic,
                                "content": text,
                            }
                        )

        except Exception as exc:  # noqa: BLE001
            logger.error("WebCrawler failed for topic %r: %s", topic, exc)

        return chunks
