"""QualityFilter — drops chunks whose content is shorter than 200 chars.

A chunk with very little text is unlikely to contribute meaningful
information to a podcast script, so we discard it early before the more
expensive TF-IDF relevance scoring step.
"""
from .base import BaseFilterStrategy

_MIN_CONTENT_LENGTH = 50


class QualityFilter(BaseFilterStrategy):
    """Accepts chunks whose ``content`` field is at least 200 characters."""

    def filter(self, chunks: list[dict]) -> list[dict]:
        """Return only chunks whose content meets the minimum length.

        Parameters
        ----------
        chunks:
            Input content chunks.

        Returns
        -------
        list[dict]
            Chunks with ``len(content) >= 200``.
        """
        return [
            chunk
            for chunk in chunks
            if len(chunk.get("content", "")) >= _MIN_CONTENT_LENGTH
        ]
