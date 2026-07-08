"""Base classes for import sources."""

from abc import ABC, abstractmethod
from pathlib import Path

from pollingapi.importer.schemas import RawPollImport


class ImportSource(ABC):
    """Convert source-specific files into raw poll import rows."""

    name: str

    @abstractmethod
    def load(self, path: Path) -> list[RawPollImport]:
        """Load import rows from a file."""
