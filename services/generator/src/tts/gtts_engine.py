"""Google TTS engine (concrete Strategy)."""

import logging

from gtts import gTTS

from src.tts.base import BaseTTSEngine

logger = logging.getLogger(__name__)

# Approximate characters per second for English speech at normal pace.
_CHARS_PER_SECOND: float = 15.0


class GTTSEngine(BaseTTSEngine):
    """Uses Google Text-to-Speech to synthesize audio."""

    def synthesize(self, text: str, output_path: str) -> float:
        """
        Synthesize *text* to an MP3 file at *output_path*.

        Args:
            text: Script to synthesize.
            output_path: Destination file path.

        Returns:
            Estimated duration in seconds (len(text) / 15.0).

        Raises:
            OSError: If the file cannot be saved.
            Exception: Any gTTS network or API error propagates unchanged.
        """
        logger.info("GTTSEngine: synthesizing %d chars → %s", len(text), output_path)
        tts = gTTS(text=text, lang="en")
        tts.save(output_path)
        duration = len(text) / _CHARS_PER_SECOND
        logger.info("GTTSEngine: saved %s (estimated %.1fs)", output_path, duration)
        return duration
