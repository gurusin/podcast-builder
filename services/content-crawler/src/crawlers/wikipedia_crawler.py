"""WikipediaCrawler — fetches content via the Wikipedia REST and Action APIs.

Uses two endpoints (no API key required):
  * ``/page/summary/{topic}``          — lead extract for the article.
  * ``/w/api.php?action=opensearch``   — search for related articles and fetch their summaries.

Both calls share a single ``httpx.AsyncClient`` with a 10-second timeout.
Network / HTTP errors are caught and logged; an empty list is returned so
that the orchestrator can continue with other crawlers.
"""
import logging
import urllib.parse

import httpx

from .base import BaseCrawler

logger = logging.getLogger(__name__)

_REST_BASE = "https://en.wikipedia.org/api/rest_v1"
_ACTION_BASE = "https://en.wikipedia.org/w/api.php"
_TIMEOUT = 10.0
_HEADERS = {"User-Agent": "podcast-builder/1.0 (https://github.com/gurusin/podcast-builder)"}
_MAX_RELATED = 4


class WikipediaCrawler(BaseCrawler):
    """Crawls Wikipedia for a topic using the public REST and Action APIs."""

    async def crawl(self, topic: str) -> list[dict]:
        """Return a list of content chunks from Wikipedia.

        Fetches the summary page and up to four related pages for *topic*.

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
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
                # 1. Summary endpoint for the main article
                summary_url = f"{_REST_BASE}/page/summary/{encoded}"
                resp = await client.get(summary_url)
                if resp.status_code == 200:
                    data = resp.json()
                    extract = data.get("extract", "").strip()
                    if extract:
                        chunks.append(
                            {
                                "url": data.get("content_urls", {})
                                .get("desktop", {})
                                .get("page", summary_url),
                                "title": data.get("title", topic),
                                "content": extract,
                            }
                        )

                # 2. OpenSearch to find related article titles
                search_params = {
                    "action": "opensearch",
                    "search": topic,
                    "limit": str(_MAX_RELATED),
                    "namespace": "0",
                    "format": "json",
                }
                resp = await client.get(_ACTION_BASE, params=search_params)
                if resp.status_code == 200:
                    search_data = resp.json()
                    # opensearch returns [query, [titles], [descriptions], [urls]]
                    titles: list[str] = search_data[1] if len(search_data) > 1 else []
                    for title in titles[:_MAX_RELATED]:
                        title_encoded = urllib.parse.quote(title, safe="")
                        related_url = f"{_REST_BASE}/page/summary/{title_encoded}"
                        r = await client.get(related_url)
                        if r.status_code == 200:
                            page = r.json()
                            extract = page.get("extract", "").strip()
                            if extract:
                                chunks.append(
                                    {
                                        "url": page.get("content_urls", {})
                                        .get("desktop", {})
                                        .get("page", related_url),
                                        "title": page.get("title", title),
                                        "content": extract,
                                    }
                                )

        except Exception as exc:  # noqa: BLE001
            logger.error("WikipediaCrawler failed for topic %r: %s", topic, exc)

        return chunks
