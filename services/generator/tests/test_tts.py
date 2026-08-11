"""Tests for TTS engine strategies."""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.tts.mock_tts_engine import MockTTSEngine
from src.tts.gtts_engine import GTTSEngine


class TestMockTTSEngine:
    def test_synthesize_creates_file(self, tmp_path):
        engine = MockTTSEngine()
        output_path = str(tmp_path / "podcast.mp3")
        engine.synthesize("Hello world", output_path)
        assert os.path.exists(output_path)

    def test_synthesize_returns_sixty(self, tmp_path):
        engine = MockTTSEngine()
        output_path = str(tmp_path / "podcast.mp3")
        duration = engine.synthesize("Some text here", output_path)
        assert duration == 60.0

    def test_synthesize_writes_non_empty_file(self, tmp_path):
        engine = MockTTSEngine()
        output_path = str(tmp_path / "podcast.mp3")
        engine.synthesize("Text", output_path)
        assert os.path.getsize(output_path) > 0

    def test_synthesize_writes_id3_header(self, tmp_path):
        engine = MockTTSEngine()
        output_path = str(tmp_path / "podcast.mp3")
        engine.synthesize("Text", output_path)
        with open(output_path, "rb") as fh:
            header = fh.read(3)
        assert header == b"ID3"

    def test_synthesize_return_type_is_float(self, tmp_path):
        engine = MockTTSEngine()
        output_path = str(tmp_path / "podcast.mp3")
        result = engine.synthesize("Text", output_path)
        assert isinstance(result, float)


class TestGTTSEngine:
    def test_gtts_called_with_correct_text(self, tmp_path):
        engine = GTTSEngine()
        text = "Hello podcast listeners!"
        output_path = str(tmp_path / "podcast.mp3")
        mock_tts_instance = MagicMock()

        with patch("src.tts.gtts_engine.gTTS", return_value=mock_tts_instance) as mock_gtts:
            engine.synthesize(text, output_path)
            mock_gtts.assert_called_once_with(text=text, lang="en")

    def test_gtts_called_with_lang_en(self, tmp_path):
        engine = GTTSEngine()
        text = "Hello!"
        output_path = str(tmp_path / "podcast.mp3")
        mock_tts_instance = MagicMock()

        with patch("src.tts.gtts_engine.gTTS", return_value=mock_tts_instance) as mock_gtts:
            engine.synthesize(text, output_path)
            _, kwargs = mock_gtts.call_args
            assert kwargs.get("lang") == "en"

    def test_gtts_save_called_with_output_path(self, tmp_path):
        engine = GTTSEngine()
        text = "Test text"
        output_path = str(tmp_path / "out.mp3")
        mock_tts_instance = MagicMock()

        with patch("src.tts.gtts_engine.gTTS", return_value=mock_tts_instance):
            engine.synthesize(text, output_path)
            mock_tts_instance.save.assert_called_once_with(output_path)

    def test_duration_is_len_text_divided_by_15(self, tmp_path):
        engine = GTTSEngine()
        text = "A" * 150  # 150 chars → 10.0s
        output_path = str(tmp_path / "out.mp3")
        mock_tts_instance = MagicMock()

        with patch("src.tts.gtts_engine.gTTS", return_value=mock_tts_instance):
            duration = engine.synthesize(text, output_path)

        assert duration == pytest.approx(len(text) / 15.0)

    def test_duration_formula_various_lengths(self, tmp_path):
        engine = GTTSEngine()
        for length in (15, 30, 300, 1500):
            text = "X" * length
            output_path = str(tmp_path / f"out_{length}.mp3")
            mock_tts_instance = MagicMock()
            with patch("src.tts.gtts_engine.gTTS", return_value=mock_tts_instance):
                duration = engine.synthesize(text, output_path)
            assert duration == pytest.approx(length / 15.0), f"Failed for length={length}"
