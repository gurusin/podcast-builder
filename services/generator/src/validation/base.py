"""Base classes for the script validation pipeline (Strategy pattern)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    passed: bool
    validator_name: str
    score: float = 1.0          # 0.0 (worst) → 1.0 (best)
    critique: str = ""          # Human-readable reason for failure


class BaseValidator(ABC):
    """Abstract base for all script validators."""

    @abstractmethod
    def validate(self, script: str, chunks: list[dict], topic: str) -> ValidationResult:
        """
        Assess a generated script against its source content.

        Args:
            script: The generated podcast script text.
            chunks: Filtered content chunks used as source material.
            topic: Podcast topic string.

        Returns:
            ValidationResult with pass/fail, numeric score, and optional critique.
        """
