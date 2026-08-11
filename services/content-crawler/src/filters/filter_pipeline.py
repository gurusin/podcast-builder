"""FilterPipeline — applies multiple filter strategies in sequence.

This is the *Pipeline* variant of the Strategy pattern: a list of
:class:`~src.filters.base.BaseFilterStrategy` objects is composed at
construction time and executed left-to-right.  The output of one strategy
is the input of the next, so ordering matters:

  1. :class:`~src.filters.quality_filter.QualityFilter` — cheapest, drops
     obviously short chunks first to reduce TF-IDF corpus size.
  2. :class:`~src.filters.deduplication_filter.DeduplicationFilter` —
     removes duplicate content before scoring.
  3. :class:`~src.filters.relevance_filter.RelevanceFilter` — expensive
     TF-IDF step runs last on the smallest possible set.

The recommended order is enforced by the
:class:`~src.container.Container`, but the pipeline itself is agnostic —
it simply calls ``strategy.filter(chunks)`` for each strategy in order.
"""
from src.filters.base import BaseFilterStrategy


class FilterPipeline:
    """Runs a sequence of filter strategies over content chunks.

    Parameters
    ----------
    strategies:
        Ordered list of :class:`BaseFilterStrategy` instances.
    """

    def __init__(self, strategies: list[BaseFilterStrategy]) -> None:
        self._strategies = strategies

    def run(self, chunks: list[dict]) -> list[dict]:
        """Pass *chunks* through every strategy in order.

        Parameters
        ----------
        chunks:
            Raw content chunks.

        Returns
        -------
        list[dict]
            Chunks that survived all strategies.
        """
        result = chunks
        for strategy in self._strategies:
            result = strategy.filter(result)
        return result
