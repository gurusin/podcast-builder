"""LLMJudgeValidator — Claude-as-judge groundedness check (optional, gated by env var).

Disabled unless ``VALIDATION_LLM_ENABLED=true`` and ``ANTHROPIC_API_KEY``
are both set.  When enabled, it sends the script and source content to
Claude Haiku and asks it to score groundedness 0.0–1.0 with a short
critique.  This step runs after the cheap deterministic gates so the API
call is only made for scripts that already meet word-count and content
safety requirements.

The LLM response is parsed for a JSON object ``{"score": float, "critique": str}``.
Any parse error or API failure is treated as a soft pass (score=0.5) to
avoid blocking podcast generation on transient infrastructure issues.
"""
import json
import logging
import os

from src.validation.base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)

_LLM_THRESHOLD = 0.60
_MODEL = "claude-haiku-4-5-20251001"
_MAX_SOURCE_CHARS = 2000  # Truncate source sent to LLM to control token cost

_PROMPT_TEMPLATE = """\
You are a podcast quality evaluator. Your task is to assess whether a generated \
podcast script is factually grounded in the provided source material.

TOPIC: {topic}

SOURCE CONTENT (excerpts from crawled web sources):
{source}

GENERATED SCRIPT:
{script}

Evaluate the script strictly:
1. Does the script accurately represent information from the source?
2. Does it introduce facts not supported by the source?
3. Does it stay on topic?

Respond with ONLY a JSON object (no markdown, no explanation outside JSON):
{{"score": <float 0.0-1.0>, "critique": "<one sentence — empty string if passed>"}}

Where 1.0 = fully grounded, 0.0 = entirely hallucinated."""


class LLMJudgeValidator(BaseValidator):
    """Calls Claude Haiku to assess script groundedness against source chunks."""

    def __init__(self) -> None:
        self._enabled = (
            os.environ.get("VALIDATION_LLM_ENABLED", "false").lower() == "true"
            and bool(os.environ.get("ANTHROPIC_API_KEY"))
        )
        if self._enabled:
            try:
                import anthropic  # noqa: PLC0415 — lazy import, optional dependency
                self._client = anthropic.Anthropic()
                logger.info("LLMJudgeValidator: enabled (model=%s)", _MODEL)
            except ImportError:
                logger.warning("LLMJudgeValidator: anthropic package not installed; disabling.")
                self._enabled = False
        else:
            logger.info(
                "LLMJudgeValidator: disabled "
                "(set VALIDATION_LLM_ENABLED=true and ANTHROPIC_API_KEY to enable)"
            )

    def validate(self, script: str, chunks: list[dict], topic: str) -> ValidationResult:
        if not self._enabled:
            return ValidationResult(
                passed=True,
                validator_name="LLMJudgeValidator",
                score=1.0,
                critique="LLM judge disabled (VALIDATION_LLM_ENABLED not set).",
            )

        source_text = " ".join(c.get("content", "") for c in chunks)[:_MAX_SOURCE_CHARS]
        prompt = _PROMPT_TEMPLATE.format(topic=topic, source=source_text, script=script)

        try:
            message = self._client.messages.create(
                model=_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            score = float(data.get("score", 0.5))
            critique = data.get("critique", "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLMJudgeValidator: API call failed (%s); soft-passing.", exc)
            return ValidationResult(
                passed=True,
                validator_name="LLMJudgeValidator",
                score=0.5,
                critique=f"LLM judge soft-pass due to error: {exc}",
            )

        passed = score >= _LLM_THRESHOLD
        return ValidationResult(
            passed=passed,
            validator_name="LLMJudgeValidator",
            score=score,
            critique=critique if not passed else "",
        )
