"""RSSCrawler — fetches content from the BBC News RSS feed.

Feed URL (no API key needed):
  ``http://feeds.bbci.co.uk/news/rss.xml``

Only entries whose title or summary contain the topic (case-insensitive
substring match) are returned.  At most the top 5 matching entries are
kept.

``feedparser`` is used for parsing; it is synchronous, so the network
call is still done with ``httpx`` (async) and the XML bytes are passed
to ``feedparser.parse`` directly.
"""
import logging

import feedparser
import httpx

from .base import BaseCrawler

logger = logging.getLogger(__name__)

_BBC_RSS_URL = "http://feeds.bbci.co.uk/news/rss.xml"
_TIMEOUT = 10.0
_MAX_RESULTS = 5


class RSSCrawler(BaseCrawler):
    """Crawls the BBC News RSS feed for entries related to a topic."""

    async def crawl(self, topic: str) -> list[dict]:
        """Return up to 5 RSS entries whose title/summary mention *topic*.

        Parameters
        ----------
        topic:
            The subject to filter entries by (case-insensitive substring
            match on ``title`` and ``summary``).

        Returns
        -------
        list[dict]
            ``[{"url": str, "title": str, "content": str}, ...]``
        """
        chunks: list[dict] = []
        topic_lower = topic.lower()

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(_BBC_RSS_URL)
                resp.raise_for_status()
                raw_bytes = resp.content

            feed = feedparser.parse(raw_bytes)

            matched = 0
            for entry in feed.entries:
                if matched >= _MAX_RESULTS:
                    break

                title: str = entry.get("title", "")
                summary: str = entry.get("summary", "")
                link: str = entry.get("link", _BBC_RSS_URL)

                if (
                    topic_lower in title.lower()
                    or topic_lower in summary.lower()
                ):
                    content = summary.strip() if summary.strip() else title
                    chunks.append(
                        {
                            "url": link,
                            "title": title,
                            "content": content,
                        }
                    )
                    matched += 1

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "RSSCrawler failed for topic %r: %s", topic, exc
            )

        return chunks
