"""WordCountValidator — deterministic gate on script word count.

Runs first in the pipeline (cheapest check) so later validators only see
scripts that meet basic length requirements.
"""
from src.validation.base import BaseValidator, ValidationResult

_BOUNDS: dict[str, tuple[int, int]] = {
    "short":  (60,   600),
    "medium": (120, 1200),
    "long":   (300, 2500),
}
_DEFAULT_BOUNDS = (100, 2500)


class WordCountValidator(BaseValidator):
    """Rejects scripts outside acceptable word-count bounds for their duration hint."""

    def __init__(self, duration_hint: str) -> None:
        self._min, self._max = _BOUNDS.get(duration_hint, _DEFAULT_BOUNDS)

    def validate(self, script: str, chunks: list[dict], topic: str) -> ValidationResult:
        count = len(script.split())
        if count < self._min:
            return ValidationResult(
                passed=False,
                validator_name="WordCountValidator",
                score=count / self._min,
                critique=f"Script too short: {count} words (minimum {self._min}).",
            )
        if count > self._max:
            return ValidationResult(
                passed=False,
                validator_name="WordCountValidator",
                score=self._max / count,
                critique=f"Script too long: {count} words (maximum {self._max}).",
            )
        return ValidationResult(
            passed=True,
            validator_name="WordCountValidator",
            score=1.0,
        )
