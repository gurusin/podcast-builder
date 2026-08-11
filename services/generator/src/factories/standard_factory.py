"""Standard (production) concrete factory."""

from src.factories.base import BasePodcastGeneratorFactory
from src.writers.base import BaseScriptWriter
from src.writers.template_script_writer import TemplateScriptWriter
from src.tts.base import BaseTTSEngine
from src.tts.gtts_engine import GTTSEngine


class StandardPodcastGeneratorFactory(BasePodcastGeneratorFactory):
    """Produces TemplateScriptWriter + GTTSEngine for production use."""

    def create_script_writer(self) -> BaseScriptWriter:
        """Return a TemplateScriptWriter instance."""
        return TemplateScriptWriter()

    def create_tts_engine(self) -> BaseTTSEngine:
        """Return a GTTSEngine instance."""
        return GTTSEngine()
