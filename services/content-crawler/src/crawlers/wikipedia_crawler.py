"""WikipediaCrawler — fetches content via the Wikipedia REST API.

Uses two endpoints (no API key required):
  * ``/page/summary/{topic}`` — returns the lead extract for the article.
  * ``/page/related/{topic}``  — returns a list of related articles.

Both calls share a single ``httpx.AsyncClient`` with a 10-second timeout.
Network / HTTP errors are caught and logged; an empty list is returned so
that the orchestrator can continue with other crawlers.
"""
import logging
import urllib.parse

import httpx

from .base import BaseCrawler

logger = logging.getLogger(__name__)

_BASE = "https://en.wikipedia.org/api/rest_v1"
_TIMEOUT = 10.0


class WikipediaCrawler(BaseCrawler):
    """Crawls Wikipedia for a topic using the public REST API."""

    async def crawl(self, topic: str) -> list[dict]:
        """Return a list of content chunks from Wikipedia.

        Fetches the summary page and up to five related pages for *topic*.

        Parameters
        ----------
        topic:
            Search topic; spaces are URL-encoded automatically.

        Returns
        -------
        list[dict]
            ``[{"url": str, "title": str, "content": str}, ...]``
        """
        encoded = urllib.parse.quote(topic, safe="")
        chunks: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                # 1. Summary endpoint
                summary_url = f"{_BASE}/page/summary/{encoded}"
                resp = await client.get(summary_url)
                if resp.status_code == 200:
                    data = resp.json()
                    extract = data.get("extract", "").strip()
                    if extract:
                        chunks.append(
                            {
                                "url": data.get(
                                    "content_urls", {}
                                )
                                .get("desktop", {})
                                .get("page", summary_url),
                                "title": data.get("title", topic),
                                "content": extract,
                            }
                        )

                # 2. Related pages endpoint
                related_url = f"{_BASE}/page/related/{encoded}"
                resp = await client.get(related_url)
                if resp.status_code == 200:
                    data = resp.json()
                    for page in data.get("pages", [])[:5]:
                        extract = page.get("extract", "").strip()
                        if extract:
                            chunks.append(
                                {
                                    "url": page.get(
                                        "content_urls", {}
                                    )
                                    .get("desktop", {})
                                    .get("page", related_url),
                                    "title": page.get("title", ""),
                                    "content": extract,
                                }
                            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "WikipediaCrawler failed for topic %r: %s", topic, exc
            )

        return chunks
