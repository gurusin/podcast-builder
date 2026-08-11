"""Narrative podcast script writer (concrete Strategy).

Produces naturally flowing spoken prose — no bracket markers that TTS
reads aloud, no robotic "Section 1:" patterns.  Chunks are ranked by
relevance score so the most on-topic content appears first.
"""
import re
from src.writers.base import BaseScriptWriter

_TARGET_WORDS: dict[str, int] = {
    "short": 350,
    "medium": 750,
    "long": 1500,
}

_CONTENT_LIMIT: dict[str, int] = {
    "short": 500,
    "medium": 700,
    "long": 1000,
}

# Minimum chars for a chunk to be considered substantive (filters DDG stubs)
_MIN_CHUNK_LENGTH = 150

_TRANSITIONS = [
    "Building on that,",
    "Another important dimension is that",
    "It's also worth highlighting that",
    "On a related note,",
    "Equally significant is the fact that",
    "Moving further into the topic,",
    "Let's explore another angle —",
    "This connects directly to another key area:",
]

# Patterns that identify disambiguation one-liners not worth narrating
_STUB_PATTERNS = [
    re.compile(r"^.{0,80}is an? (album|EP|film|movie|book|series|journal|compilation|game)\b", re.I),
    re.compile(r"^.{0,80}released (on|by|in) \d{4}\b", re.I),
]


def _is_stub(content: str) -> bool:
    for pat in _STUB_PATTERNS:
        if pat.match(content.strip()):
            return True
    return False


def _trim_to_sentence(text: str, limit: int) -> str:
    """Trim text to at most *limit* chars, ending at a sentence boundary."""
    if len(text) <= limit:
        return text
    snippet = text[:limit]
    for terminator in (".", "?", "!"):
        idx = snippet.rfind(terminator)
        if idx > limit // 2:
            return snippet[: idx + 1]
    return snippet.rstrip() + "."


def _clean_content(content: str, title: str) -> str:
    """Strip a leading title prefix that Wikipedia/DDG often prepends."""
    stripped = content.strip()
    if title and stripped.lower().startswith(title.lower()):
        stripped = stripped[len(title):].lstrip(" —:-\t").strip()
    return stripped if stripped else content.strip()


class TemplateScriptWriter(BaseScriptWriter):
    """Builds a naturally spoken podcast script from ranked content chunks."""

    def write(self, topic: str, chunks: list[dict], duration_hint: str, attempt: int = 1) -> str:
        """
        Produce a spoken-word podcast script.

        Args:
            topic: Podcast subject.
            chunks: Filtered content dicts with keys url, title, content, score.
            duration_hint: 'short' | 'medium' | 'long'.
            attempt: Retry attempt (1-based). Higher attempts expand content_limit
                     by 50% per attempt so more source text is included, improving
                     the chance of passing groundedness validation.

        Returns:
            Multi-sentence script suitable for TTS synthesis.
        """
        target_words = _TARGET_WORDS.get(duration_hint, _TARGET_WORDS["medium"])
        base_content_limit = _CONTENT_LIMIT.get(duration_hint, _CONTENT_LIMIT["medium"])
        # Expand content limit on retries to pull in more source material
        content_limit = int(base_content_limit * (1.0 + 0.5 * (attempt - 1)))

        # Rank by relevance score, drop stubs and very short entries.
        # Chunks with no score are primary sources (Wikipedia main article);
        # float("inf") ensures they always lead.
        ranked = sorted(
            [
                c for c in chunks
                if len(c.get("content", "")) >= _MIN_CHUNK_LENGTH
                and not _is_stub(c.get("content", ""))
            ],
            key=lambda c: c["score"] if c.get("score") is not None else float("inf"),
            reverse=True,
        )

        sentences: list[str] = []

        # Intro — warm, spoken naturally
        sentences.append(
            f"Welcome to today's episode, where we take a closer look at {topic}. "
            f"This is a topic that has been generating a lot of interest lately, "
            f"and there is plenty to unpack. Let's get into it."
        )

        word_count = len(sentences[0].split())
        transition_idx = 0

        for i, chunk in enumerate(ranked):
            if word_count >= target_words:
                break

            raw = chunk.get("content", "")
            title = chunk.get("title", "")
            content = _clean_content(raw, title)
            snippet = _trim_to_sentence(content, content_limit)

            if not snippet:
                continue

            # Decide whether naming the article/source adds value
            source_is_topic = title.lower().strip() == topic.lower().strip()
            title_in_snippet = title.lower().strip() in snippet.lower()[:80]

            if i == 0:
                # Lead paragraph — no transition, integrate naturally
                if not source_is_topic and not title_in_snippet and title:
                    block = f"According to {title}: {snippet}"
                else:
                    block = snippet
            else:
                transition = _TRANSITIONS[transition_idx % len(_TRANSITIONS)]
                transition_idx += 1
                if not source_is_topic and not title_in_snippet and title:
                    block = f"{transition} When it comes to {title} — {snippet}"
                else:
                    block = f"{transition} {snippet}"

            sentences.append(block)
            word_count += len(block.split())

        # Fallback if no chunks survived filtering
        if len(sentences) == 1:
            sentences.append(
                f"While detailed sources were not available at this time, "
                f"{topic} remains a rapidly evolving field with broad implications "
                f"across technology, society, and industry. "
                f"We encourage you to explore further through trusted resources."
            )

        # Outro
        sentences.append(
            f"That brings us to the end of today's episode on {topic}. "
            f"Thank you for listening. We hope this gave you a clear and useful overview. "
            f"Until next time, keep learning."
        )

        # Two spaces between paragraphs = natural TTS pause
        return "  ".join(sentences)
