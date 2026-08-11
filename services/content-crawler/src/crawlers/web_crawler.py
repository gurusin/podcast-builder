"""WebCrawler — fetches content via the DuckDuckGo Instant Answer API.

Endpoint (no API key needed):
  ``https://api.duckduckgo.com/?q={topic}&format=json&no_redirect=1``

Parsed fields:
  * ``AbstractText`` — a summary paragraph (if present).
  * ``RelatedTopics[].Text`` — short related topic snippets.

Network / HTTP errors are caught and logged; an empty list is returned.
"""
import logging
import urllib.parse

import httpx

from .base import BaseCrawler

logger = logging.getLogger(__name__)

_DDG_URL = "https://api.duckduckgo.com/"
_TIMEOUT = 10.0


class WebCrawler(BaseCrawler):
    """Crawls DuckDuckGo Instant Answers for a topic."""

    async def crawl(self, topic: str) -> list[dict]:
        """Return content chunks scraped from DuckDuckGo Instant Answers.

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
        params = {
            "q": topic,
            "format": "json",
            "no_redirect": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(_DDG_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Abstract / summary text
            abstract_text = data.get("AbstractText", "").strip()
            abstract_url = data.get("AbstractURL", _DDG_URL)
            abstract_source = data.get("AbstractSource", "DuckDuckGo")
            if abstract_text:
                chunks.append(
                    {
                        "url": abstract_url,
                        "title": f"{abstract_source}: {topic}",
                        "content": abstract_text,
                    }
                )

            # Related topics
            for item in data.get("RelatedTopics", []):
                # Items can be groups (have "Topics" key) or plain dicts
                if "Topics" in item:
                    for sub in item["Topics"]:
                        text = sub.get("Text", "").strip()
                        if text:
                            chunks.append(
                                {
                                    "url": sub.get(
                                        "FirstURL",
                                        f"{_DDG_URL}?q={urllib.parse.quote(topic)}",
                                    ),
                                    "title": topic,
                                    "content": text,
                                }
                            )
                else:
                    text = item.get("Text", "").strip()
                    if text:
                        chunks.append(
                            {
                                "url": item.get(
                                    "FirstURL",
                                    f"{_DDG_URL}?q={urllib.parse.quote(topic)}",
                                ),
                                "title": topic,
                                "content": text,
                            }
                        )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "WebCrawler failed for topic %r: %s", topic, exc
            )

        return chunks
