"""Built-in import source registry."""

from pollingapi.importer.sources.base import ImportSource
from pollingapi.importer.sources.csv import CsvImportSource

SOURCES: dict[str, type[ImportSource]] = {
    CsvImportSource.name: CsvImportSource,
    "manual_csv": CsvImportSource,
}


def get_source(name: str) -> ImportSource:
    """Return a configured import source by name."""
    try:
        return SOURCES[name]()
    except KeyError as exc:
        raise ValueError(f"Import source '{name}' not found") from exc


def list_sources() -> list[str]:
    """List available import source names."""
    return sorted(SOURCES)
