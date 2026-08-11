"""Template-based podcast script writer (concrete Strategy)."""

from src.writers.base import BaseScriptWriter

_SECTIONS_BY_HINT: dict[str, int] = {
    "short": 3,
    "medium": 5,
    "long": 8,
}

_CONTENT_SNIPPET_LEN = 300


class TemplateScriptWriter(BaseScriptWriter):
    """Builds a structured podcast script from a fixed template."""

    def write(self, topic: str, chunks: list[dict], duration_hint: str) -> str:
        """
        Build a structured podcast script.

        Args:
            topic: The podcast subject.
            chunks: List of content dicts (keys: url, title, content, score).
            duration_hint: 'short' → 3 sections, 'medium' → 5, 'long' → 8.

        Returns:
            Multi-line podcast script string.
        """
        num_sections = _SECTIONS_BY_HINT.get(duration_hint, _SECTIONS_BY_HINT["medium"])

        lines: list[str] = []

        # INTRO
        lines.append(
            f"[INTRO] Welcome to today's podcast about {topic}. "
            f"We have an exciting set of stories and insights prepared for you."
        )

        # SECTIONS
        for section_idx in range(1, num_sections + 1):
            if chunks and section_idx <= len(chunks):
                chunk = chunks[section_idx - 1]
                title = chunk.get("title", f"Topic {section_idx}")
                content = chunk.get("content", "")
                snippet = content[:_CONTENT_SNIPPET_LEN].strip()
                if len(content) > _CONTENT_SNIPPET_LEN:
                    snippet += "..."
            else:
                title = f"Insight {section_idx}"
                snippet = (
                    f"This segment explores key aspects of {topic} "
                    f"that are shaping the landscape today."
                )

            lines.append(
                f"[SECTION {section_idx}] {title}: {snippet}"
            )

        # OUTRO
        lines.append(
            f"[OUTRO] That wraps up today's episode on {topic}. "
            f"Thank you for listening and we hope to see you next time."
        )

        return "\n\n".join(lines)
