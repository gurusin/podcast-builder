"""Tests for TemplateScriptWriter (Strategy pattern)."""

import pytest

from src.writers.template_script_writer import TemplateScriptWriter


@pytest.fixture()
def writer() -> TemplateScriptWriter:
    return TemplateScriptWriter()


@pytest.fixture()
def sample_chunks() -> list[dict]:
    return [
        {"url": "https://example.com/1", "title": f"Article {i}", "content": f"Content {i} " * 50, "score": 0.9}
        for i in range(1, 10)
    ]


class TestTemplateScriptWriter:
    def test_write_short_contains_intro(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "short")
        assert "[INTRO]" in script

    def test_write_short_contains_section(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "short")
        assert "[SECTION" in script

    def test_write_short_contains_outro(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "short")
        assert "[OUTRO]" in script

    def test_write_short_contains_topic(self, writer, sample_chunks):
        topic = "Quantum Computing"
        script = writer.write(topic, sample_chunks, "short")
        assert topic in script

    def test_write_short_produces_at_most_three_sections(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "short")
        section_count = script.count("[SECTION")
        assert section_count <= 3

    def test_write_short_produces_exactly_three_sections(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "short")
        section_count = script.count("[SECTION")
        assert section_count == 3

    def test_write_long_produces_eight_sections(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "long")
        section_count = script.count("[SECTION")
        assert section_count == 8

    def test_write_medium_produces_five_sections(self, writer, sample_chunks):
        script = writer.write("AI Trends", sample_chunks, "medium")
        section_count = script.count("[SECTION")
        assert section_count == 5

    def test_write_empty_chunks_does_not_crash(self, writer):
        script = writer.write("Blockchain", [], "short")
        assert "[INTRO]" in script
        assert "[OUTRO]" in script

    def test_write_empty_chunks_still_has_sections(self, writer):
        script = writer.write("Blockchain", [], "short")
        assert "[SECTION" in script

    def test_intro_mentions_topic(self, writer, sample_chunks):
        topic = "Space Exploration"
        script = writer.write(topic, sample_chunks, "short")
        intro_line = [line for line in script.split("\n\n") if "[INTRO]" in line][0]
        assert topic in intro_line

    def test_outro_mentions_topic(self, writer, sample_chunks):
        topic = "Space Exploration"
        script = writer.write(topic, sample_chunks, "short")
        outro_line = [line for line in script.split("\n\n") if "[OUTRO]" in line][0]
        assert topic in outro_line

    def test_section_includes_chunk_title(self, writer):
        chunks = [{"url": "u", "title": "Unique Title XYZ", "content": "body", "score": 1.0}]
        script = writer.write("Tech", chunks, "short")
        assert "Unique Title XYZ" in script

    def test_section_snippet_truncated_at_300_chars(self, writer):
        long_content = "A" * 500
        chunks = [{"url": "u", "title": "T", "content": long_content, "score": 1.0}]
        script = writer.write("Tech", chunks, "short")
        # The snippet should contain "..." to indicate truncation
        assert "..." in script
