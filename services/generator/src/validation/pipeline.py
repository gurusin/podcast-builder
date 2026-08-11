"""ValidationPipeline — runs validators in sequence, short-circuits on failure.

Order matters: cheap deterministic gates run first so the more expensive
groundedness and LLM-judge steps are only reached by scripts that already
pass basic sanity checks.

Funnel:
  WordCountValidator  (O(n) word split, nanoseconds)
  BannedContentValidator  (regex scan, microseconds)
  GroundednessValidator   (TF-IDF, milliseconds)
  LLMJudgeValidator       (API call, seconds — only if VALIDATION_LLM_ENABLED)
"""
import logging

from src.validation.base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """Runs a sequence of validators and returns the first failure or a combined pass."""

    def __init__(self, validators: list[BaseValidator]) -> None:
        self._validators = validators

    def validate(self, script: str, chunks: list[dict], topic: str) -> ValidationResult:
        """Run all validators in order.

        Returns the first failing ValidationResult, or the last result if all pass.
        """
        last: ValidationResult | None = None
        for validator in self._validators:
            result = validator.validate(script, chunks, topic)
            logger.debug(
                "ValidationPipeline: %s → passed=%s score=%.3f",
                result.validator_name,
                result.passed,
                result.score,
            )
            last = result
            if not result.passed:
                logger.warning(
                    "ValidationPipeline: FAILED at %s — %s",
                    result.validator_name,
                    result.critique,
                )
                return result

        return last or ValidationResult(passed=True, validator_name="ValidationPipeline", score=1.0)
