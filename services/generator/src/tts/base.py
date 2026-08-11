"""Base abstract class for TTS engines (Strategy pattern)."""

from abc import ABC, abstractmethod


class BaseTTSEngine(ABC):
    """Abstract base for all text-to-speech synthesis strategies."""

    @abstractmethod
    def synthesize(self, text: str, output_path: str) -> float:
        """
        Convert text to speech and save to output_path.

        Args:
            text: The script text to synthesize.
            output_path: Absolute filesystem path for the output MP3 file.

        Returns:
            Estimated duration in seconds.
        """
