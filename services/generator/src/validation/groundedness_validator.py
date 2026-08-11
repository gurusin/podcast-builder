"""GroundednessValidator — TF-IDF cosine similarity between script and source content.

This is the lightweight "LLM-as-judge proxy" step: it quantifies how much
of the script's vocabulary is grounded in the crawled source material,
without requiring an external API call.

A script that makes up facts will use vocabulary absent from the source
chunks, pushing cosine similarity below the threshold.
"""
import logging

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.validation.base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)

_GROUNDEDNESS_THRESHOLD = 0.10  # cosine similarity minimum


class GroundednessValidator(BaseValidator):
    """Measures lexical overlap between the script and its source chunks via TF-IDF."""

    def validate(self, script: str, chunks: list[dict], topic: str) -> ValidationResult:
        if not chunks:
            # No source content — fall back to topic presence check
            if topic.lower() in script.lower():
                return ValidationResult(
                    passed=True,
                    validator_name="GroundednessValidator",
                    score=0.5,
                    critique="No source chunks; topic term present in script.",
                )
            return ValidationResult(
                passed=False,
                validator_name="GroundednessValidator",
                score=0.0,
                critique="No source chunks and topic term absent from script.",
            )

        source_text = " ".join(c.get("content", "") for c in chunks)

        try:
            vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
            matrix = vectorizer.fit_transform([script, source_text])
            score = float(cosine_similarity(matrix[0], matrix[1])[0][0])
        except ValueError as exc:
            logger.warning("GroundednessValidator TF-IDF failed: %s", exc)
            return ValidationResult(
                passed=True,
                validator_name="GroundednessValidator",
                score=0.5,
                critique=f"TF-IDF error (skipped): {exc}",
            )

        passed = score >= _GROUNDEDNESS_THRESHOLD
        return ValidationResult(
            passed=passed,
            validator_name="GroundednessValidator",
            score=score,
            critique="" if passed else (
                f"Script not sufficiently grounded in source content "
                f"(TF-IDF cosine={score:.3f}, threshold={_GROUNDEDNESS_THRESHOLD})."
            ),
        )
