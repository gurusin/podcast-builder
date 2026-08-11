"""Abstract Factory base for podcast generator component families."""

from abc import ABC, abstractmethod

from src.writers.base import BaseScriptWriter
from src.tts.base import BaseTTSEngine


class BasePodcastGeneratorFactory(ABC):
    """
    Abstract Factory that produces matched pairs of ScriptWriter and TTSEngine.

    Concrete factories guarantee that the writer and engine returned are
    compatible and intended to be used together.
    """

    @abstractmethod
    def create_script_writer(self) -> BaseScriptWriter:
        """Return a concrete BaseScriptWriter instance."""

    @abstractmethod
    def create_tts_engine(self) -> BaseTTSEngine:
        """Return a concrete BaseTTSEngine instance."""
