"""Mock concrete factory — used in tests to avoid network/audio calls."""

from src.factories.base import BasePodcastGeneratorFactory
from src.writers.base import BaseScriptWriter
from src.writers.template_script_writer import TemplateScriptWriter
from src.tts.base import BaseTTSEngine
from src.tts.mock_tts_engine import MockTTSEngine


class MockPodcastGeneratorFactory(BasePodcastGeneratorFactory):
    """Produces TemplateScriptWriter + MockTTSEngine for testing."""

    def create_script_writer(self) -> BaseScriptWriter:
        """Return a TemplateScriptWriter instance."""
        return TemplateScriptWriter()

    def create_tts_engine(self) -> BaseTTSEngine:
        """Return a MockTTSEngine instance (no network calls)."""
        return MockTTSEngine()
