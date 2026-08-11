"""Base filter strategy abstract class (Strategy pattern).

``BaseFilterStrategy`` defines the contract that every concrete filter
must satisfy.  The :class:`~src.filters.filter_pipeline.FilterPipeline`
composes multiple strategies and applies them in order, giving us the
*Pipeline* variant of the Strategy pattern.
"""
from abc import ABC, abstractmethod


class BaseFilterStrategy(ABC):
    """Abstract base for content-chunk filter strategies.

    Each strategy receives a list of chunk dicts and returns a (possibly
    shorter) list that has passed the strategy's acceptance criterion.
    Strategies must not mutate the original dicts; they may return new
    dicts with additional keys (e.g. ``score``).
    """

    @abstractmethod
    def filter(self, chunks: list[dict]) -> list[dict]:
        """Apply the filter and return only the accepted chunks.

        Parameters
        ----------
        chunks:
            Input list of ``{"url": str, "title": str, "content": str}``
            dicts (may carry extra keys added by prior strategies).

        Returns
        -------
        list[dict]
            The subset of *chunks* accepted by this strategy.
        """
