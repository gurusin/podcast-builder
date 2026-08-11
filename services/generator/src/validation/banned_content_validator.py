"""BannedContentValidator — deterministic keyword blocklist gate.

Runs before any scoring step.  Blocked content should never be synthesised
to audio regardless of groundedness or length.
"""
import re

from src.validation.base import BaseValidator, ValidationResult

_BANNED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(fuck|shit|cunt|nigger|faggot)\b", re.I),
    re.compile(r"\b(kill (yourself|urself)|kys)\b", re.I),
    re.compile(r"\b(bomb|explosive|terrorism|genocide)\b.*\b(how to|instructions|guide)\b", re.I),
]


class BannedContentValidator(BaseValidator):
    """Fails immediately if the script matches any banned content pattern."""

    def validate(self, script: str, chunks: list[dict], topic: str) -> ValidationResult:
        for pat in _BANNED_PATTERNS:
            match = pat.search(script)
            if match:
                return ValidationResult(
                    passed=False,
                    validator_name="BannedContentValidator",
                    score=0.0,
                    critique=f"Script contains banned content matching pattern: {pat.pattern!r}.",
                )
        return ValidationResult(passed=True, validator_name="BannedContentValidator", score=1.0)
