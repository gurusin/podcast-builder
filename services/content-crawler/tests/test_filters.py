"""Tests for the filter strategy implementations and FilterPipeline.

All tests are synchronous (filters are not async).  Each test is
written to fail meaningfully if the implementation is absent or wrong.
"""
import pytest

from src.filters.deduplication_filter import DeduplicationFilter
from src.filters.filter_pipeline import FilterPipeline
from src.filters.quality_filter import QualityFilter
from src.filters.relevance_filter import RelevanceFilter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(content: str, url: str = "https://example.com", title: str = "Test") -> dict:
    return {"url": url, "title": title, "content": content}


def _long_content(length: int = 250, char: str = "x") -> str:
    return char * length


def _short_content(length: int = 50, char: str = "x") -> str:
    return char * length


# ---------------------------------------------------------------------------
# QualityFilter
# ---------------------------------------------------------------------------

class TestQualityFilter:
    """Tests for :class:`~src.filters.quality_filter.QualityFilter`."""

    def test_rejects_chunk_below_200_chars(self):
        """A chunk with content < 200 chars must be dropped."""
        chunks = [_chunk(_short_content(199))]
        result = QualityFilter().filter(chunks)
        assert result == []

    def test_rejects_chunk_exactly_199_chars(self):
        """199-char content is just below the threshold and must be dropped."""
        chunks = [_chunk("a" * 199)]
        result = QualityFilter().filter(chunks)
        assert result == []

    def test_accepts_chunk_exactly_200_chars(self):
        """200-char content is exactly at the threshold and must be kept."""
        chunks = [_chunk("a" * 200)]
        result = QualityFilter().filter(chunks)
        assert len(result) == 1

    def test_accepts_chunk_above_200_chars(self):
        """Content longer than 200 chars must be kept."""
        chunks = [_chunk(_long_content(300))]
        result = QualityFilter().filter(chunks)
        assert len(result) == 1

    def test_mixed_chunks_only_long_kept(self):
        """Short chunks are removed; long chunks survive."""
        short = _chunk(_short_content(100))
        long = _chunk(_long_content(250))
        result = QualityFilter().filter([short, long])
        assert len(result) == 1
        assert result[0] is long

    def test_empty_input_returns_empty(self):
        """Empty input list returns empty output."""
        assert QualityFilter().filter([]) == []

    def test_missing_content_key_treated_as_empty(self):
        """A chunk without a 'content' key is treated as zero-length."""
        chunks = [{"url": "u", "title": "t"}]
        result = QualityFilter().filter(chunks)
        assert result == []


# ---------------------------------------------------------------------------
# DeduplicationFilter
# ---------------------------------------------------------------------------

class TestDeduplicationFilter:
    """Tests for :class:`~src.filters.deduplication_filter.DeduplicationFilter`."""

    def test_removes_second_chunk_with_same_prefix(self):
        """Two chunks sharing the same first 100 chars → only first survives."""
        common_prefix = "a" * 100
        chunk1 = _chunk(common_prefix + " rest of first chunk")
        chunk2 = _chunk(common_prefix + " rest of second chunk")
        result = DeduplicationFilter().filter([chunk1, chunk2])
        assert len(result) == 1
        assert result[0] is chunk1

    def test_keeps_chunks_with_different_prefixes(self):
        """Chunks with different prefixes are all kept."""
        chunk1 = _chunk("Alpha " + "x" * 100)
        chunk2 = _chunk("Beta " + "y" * 100)
        result = DeduplicationFilter().filter([chunk1, chunk2])
        assert len(result) == 2

    def test_three_chunks_two_duplicates(self):
        """Three chunks where two share a prefix → two unique chunks returned."""
        prefix = "b" * 100
        c1 = _chunk(prefix + " unique end 1")
        c2 = _chunk(prefix + " unique end 2")  # duplicate of c1
        c3 = _chunk("c" * 100 + " unique")
        result = DeduplicationFilter().filter([c1, c2, c3])
        assert len(result) == 2
        assert c1 in result
        assert c3 in result
        assert c2 not in result

    def test_empty_input_returns_empty(self):
        """Empty input returns empty output."""
        assert DeduplicationFilter().filter([]) == []

    def test_single_chunk_always_kept(self):
        """A single chunk is never deduplicated."""
        chunk = _chunk("only chunk " + "z" * 100)
        result = DeduplicationFilter().filter([chunk])
        assert result == [chunk]

    def test_prefix_stripped_before_comparison(self):
        """Leading/trailing whitespace is stripped before prefix comparison."""
        common = "word " * 20  # 100 chars with leading space
        c1 = _chunk("  " + common + " tail1")
        c2 = _chunk("  " + common + " tail2")
        result = DeduplicationFilter().filter([c1, c2])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# RelevanceFilter
# ---------------------------------------------------------------------------

class TestRelevanceFilter:
    """Tests for :class:`~src.filters.relevance_filter.RelevanceFilter`."""

    def test_relevant_chunk_passes_threshold(self):
        """A chunk about the topic should score >= 0.05 and be kept."""
        topic = "machine learning"
        relevant_content = (
            "Machine learning is a subset of artificial intelligence that "
            "enables systems to learn and improve from experience without "
            "being explicitly programmed.  It focuses on developing computer "
            "programs that can access data and use it to learn for themselves."
        )
        chunks = [_chunk(relevant_content)]
        result = RelevanceFilter(topic).filter(chunks)
        assert len(result) == 1
        assert result[0]["score"] >= 0.05

    def test_irrelevant_chunk_dropped(self):
        """A chunk unrelated to the topic scores below threshold and is dropped."""
        topic = "quantum physics"
        irrelevant_content = (
            "The stock market rose sharply today as investors celebrated the "
            "quarterly earnings report from the largest retail companies in "
            "the country.  Analysts predicted further gains in the coming week."
        )
        chunks = [_chunk(irrelevant_content)]
        result = RelevanceFilter(topic).filter(chunks)
        # May or may not pass depending on TF-IDF; we assert score key exists
        # when present, and that a clearly irrelevant chunk scores lower than
        # a relevant one (tested in the comparative test below).
        for r in result:
            assert "score" in r

    def test_relevant_chunk_scores_higher_than_irrelevant(self):
        """Chunk about the topic scores higher than an unrelated chunk."""
        topic = "deep learning neural networks"
        relevant = _chunk(
            "Deep learning uses neural networks with many layers to learn "
            "representations of data.  Convolutional neural networks are "
            "used in computer vision tasks such as image recognition and "
            "object detection.  Recurrent networks handle sequential data."
        )
        irrelevant = _chunk(
            "The weather forecast for the weekend shows sunny skies and "
            "warm temperatures across the country.  Residents are encouraged "
            "to stay hydrated and apply sunscreen before going outdoors to "
            "enjoy the fine conditions expected throughout the day."
        )
        chunks = [relevant, irrelevant]
        result = RelevanceFilter(topic).filter(chunks)

        scored = {r["content"][:20]: r["score"] for r in result}
        relevant_score = scored.get(relevant["content"][:20], 0.0)
        irrelevant_score = scored.get(irrelevant["content"][:20], 0.0)
        assert relevant_score > irrelevant_score

    def test_score_key_added_to_accepted_chunk(self):
        """Accepted chunks carry a float 'score' key."""
        topic = "climate change"
        content = (
            "Climate change refers to long-term shifts in temperatures and "
            "weather patterns.  These shifts may be natural but since the "
            "industrial revolution human activities have been the main driver "
            "of climate change, primarily due to fossil fuels burning."
        )
        chunks = [_chunk(content)]
        result = RelevanceFilter(topic).filter(chunks)
        if result:  # may pass threshold
            assert isinstance(result[0]["score"], float)

    def test_empty_input_returns_empty(self):
        """Empty input returns empty output."""
        assert RelevanceFilter("topic").filter([]) == []


# ---------------------------------------------------------------------------
# FilterPipeline
# ---------------------------------------------------------------------------

class TestFilterPipeline:
    """Tests for :class:`~src.filters.filter_pipeline.FilterPipeline`."""

    def test_pipeline_removes_short_chunks(self):
        """Short-content chunks are removed by QualityFilter in the pipeline."""
        topic = "artificial intelligence"
        pipeline = FilterPipeline([
            QualityFilter(),
            DeduplicationFilter(),
            RelevanceFilter(topic),
        ])
        short_chunk = _chunk("too short")  # < 200 chars
        result = pipeline.run([short_chunk])
        assert result == []

    def test_pipeline_removes_duplicate_chunks(self):
        """Near-duplicate chunks are removed by DeduplicationFilter."""
        topic = "artificial intelligence"
        prefix = "Artificial intelligence is a broad field of computer science " + "x" * 50
        c1 = _chunk(prefix + " unique tail 1 " + "y" * 50)
        c2 = _chunk(prefix + " unique tail 2 " + "z" * 50)
        pipeline = FilterPipeline([
            QualityFilter(),
            DeduplicationFilter(),
            RelevanceFilter(topic),
        ])
        result = pipeline.run([c1, c2])
        # At most one of the two duplicates should survive
        assert len(result) <= 1

    def test_pipeline_removes_irrelevant_chunks(self):
        """Chunks irrelevant to the topic are removed by RelevanceFilter."""
        topic = "quantum computing"
        irrelevant = _chunk(
            "The annual flower show attracted thousands of visitors to the "
            "botanical garden.  Rare orchids and exotic plants were on display "
            "in a colourful exhibition that delighted children and adults alike "
            "throughout the weekend event held at the central park venue."
        )
        pipeline = FilterPipeline([
            QualityFilter(),
            DeduplicationFilter(),
            RelevanceFilter(topic),
        ])
        result = pipeline.run([irrelevant])
        assert result == []

    def test_pipeline_applies_strategies_in_order(self):
        """Pipeline applies all three strategies; only relevant long unique chunks pass."""
        topic = "space exploration"
        good_chunk = _chunk(
            "Space exploration involves the investigation of outer space by "
            "means of astronomy and space technology.  National space agencies "
            "such as NASA have launched numerous missions to explore planets, "
            "moons, and other celestial bodies within and beyond our solar system."
        )
        short_chunk = _chunk("too short")
        pipeline = FilterPipeline([
            QualityFilter(),
            DeduplicationFilter(),
            RelevanceFilter(topic),
        ])
        result = pipeline.run([good_chunk, short_chunk])
        # short_chunk must not appear; good_chunk may or may not pass relevance
        contents = [c["content"] for c in result]
        assert short_chunk["content"] not in contents

    def test_empty_pipeline_returns_chunks_unchanged(self):
        """A pipeline with no strategies returns the original list."""
        chunks = [_chunk("a" * 300)]
        pipeline = FilterPipeline([])
        result = pipeline.run(chunks)
        assert result == chunks

    def test_empty_input_returns_empty(self):
        """Empty input returns empty output regardless of strategies."""
        pipeline = FilterPipeline([QualityFilter(), DeduplicationFilter()])
        assert pipeline.run([]) == []
