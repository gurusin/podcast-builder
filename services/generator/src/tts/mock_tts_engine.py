"""Mock TTS engine for testing — no network calls."""

import logging

from src.tts.base import BaseTTSEngine

logger = logging.getLogger(__name__)

# A minimal valid ID3 header so file-existence checks see a non-empty file.
_MOCK_MP3_HEADER: bytes = b"ID3"

_MOCK_DURATION_SECS: float = 60.0


class MockTTSEngine(BaseTTSEngine):
    """Writes a stub MP3 file without any network call. Always returns 60.0s."""

    def synthesize(self, text: str, output_path: str) -> float:
        """
        Write a minimal MP3 stub to *output_path* and return a fixed duration.

        Args:
            text: Script text (ignored — no real synthesis is performed).
            output_path: Destination file path.

        Returns:
            60.0 (fixed mock duration).

        Raises:
            OSError: If the file cannot be written.
        """
        logger.debug("MockTTSEngine: writing stub MP3 to %s", output_path)
        with open(output_path, "wb") as fh:
            fh.write(_MOCK_MP3_HEADER)
        return _MOCK_DURATION_SECS
