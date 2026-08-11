"""Base abstract class for script writers (Strategy pattern)."""

from abc import ABC, abstractmethod


class BaseScriptWriter(ABC):
    """Abstract base for all script-writing strategies."""

    @abstractmethod
    def write(self, topic: str, chunks: list[dict], duration_hint: str, attempt: int = 1) -> str:
        """
        Produce a podcast script string.

        Args:
            topic: The podcast subject.
            chunks: List of content dicts with keys url, title, content, score.
            duration_hint: One of 'short', 'medium', 'long'.
            attempt: Retry attempt number (1-based). Writers may expand
                     content limits on higher attempt numbers to pass
                     groundedness validation.

        Returns:
            A formatted podcast script string.
        """
