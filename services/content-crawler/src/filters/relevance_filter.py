"""RelevanceFilter — scores chunks using TF-IDF cosine similarity.

Each chunk's ``content`` is compared against the topic string using
scikit-learn's ``TfidfVectorizer`` + ``cosine_similarity``.  Chunks
scoring below ``RELEVANCE_THRESHOLD`` (0.05) are discarded; accepted
chunks receive an additional ``score`` key.

Design note (Strategy pattern): the topic is injected at construction
time, making ``RelevanceFilter`` a *parameterised* strategy.  The
:class:`~src.filters.filter_pipeline.FilterPipeline` therefore treats it
identically to the other zero-argument strategies.
"""
import logging
from typing import Final

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import BaseFilterStrategy

logger = logging.getLogger(__name__)

RELEVANCE_THRESHOLD: Final[float] = 0.05


class RelevanceFilter(BaseFilterStrategy):
    """Accepts chunks whose TF-IDF cosine similarity to the topic >= 0.05.

    Parameters
    ----------
    topic:
        The subject of the podcast episode; used as the reference document
        for TF-IDF similarity scoring.
    """

    def __init__(self, topic: str) -> None:
        self._topic = topic

    def filter(self, chunks: list[dict]) -> list[dict]:
        """Score each chunk and return only sufficiently relevant ones.

        Parameters
        ----------
        chunks:
            Input content chunks.

        Returns
        -------
        list[dict]
            Chunks whose cosine similarity score >= ``RELEVANCE_THRESHOLD``.
            Each accepted chunk carries an extra ``"score"`` key (float).
        """
        if not chunks:
            return []

        contents = [chunk.get("content", "") for chunk in chunks]
        corpus = [self._topic] + contents  # index 0 = topic vector

        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(corpus)
        except ValueError as exc:
            # Happens when all tokens are stop-words (empty vocab)
            logger.warning("RelevanceFilter TF-IDF failed: %s", exc)
            return []

        topic_vector = tfidf_matrix[0]
        content_vectors = tfidf_matrix[1:]
        scores = cosine_similarity(topic_vector, content_vectors).flatten()

        result: list[dict] = []
        for chunk, score in zip(chunks, scores):
            if score >= RELEVANCE_THRESHOLD:
                result.append({**chunk, "score": float(score)})

        return result
