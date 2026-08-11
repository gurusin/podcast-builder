"""DeduplicationFilter — removes near-duplicate chunks.

Two chunks are considered near-duplicates if the first 100 characters of
their ``content`` fields are identical (after stripping leading/trailing
whitespace).  Only the first occurrence is kept.

This simple prefix-based heuristic is O(n) and avoids the cost of full
pairwise comparison while catching the most common case: the same article
appearing in both a Wikipedia summary and an RSS feed snippet.
"""
from .base import BaseFilterStrategy

_PREFIX_LENGTH = 100


class DeduplicationFilter(BaseFilterStrategy):
    """Drops chunks that share the same content prefix as an earlier chunk."""

    def filter(self, chunks: list[dict]) -> list[dict]:
        """Return chunks with unique content prefixes (first 100 chars).

        Parameters
        ----------
        chunks:
            Input content chunks.

        Returns
        -------
        list[dict]
            De-duplicated chunks preserving original order.
        """
        seen: set[str] = set()
        result: list[dict] = []

        for chunk in chunks:
            prefix = chunk.get("content", "").strip()[:_PREFIX_LENGTH]
            if prefix not in seen:
                seen.add(prefix)
                result.append(chunk)

        return result
