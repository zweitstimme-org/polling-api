"""Importer orchestration."""

from pathlib import Path

from sqlalchemy.orm import Session

from pollingapi.cleaner import run_cleaning_pipeline
from pollingapi.core import PROJECT_ROOT
from pollingapi.importer.insertion import insert_raw_polls
from pollingapi.importer.schemas import ImportResult, ImportStats, RawPollImport
from pollingapi.importer.sources import get_source, list_sources
from pollingapi.logging_config import get_logger

IMPORTS_DIR = PROJECT_ROOT / "imports"
logger = get_logger(__name__)


class ImportRunner:
    """Run file imports into polls_raw and optionally clean them."""

    def __init__(self, db: Session, imports_dir: Path = IMPORTS_DIR):
        self.db = db
        self.imports_dir = imports_dir

    def resolve_path(self, path: Path | str) -> Path:
        """Resolve import paths relative to the top-level imports directory."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.imports_dir / candidate
        return candidate

    def list_sources(self) -> list[str]:
        """List available importer sources."""
        return list_sources()

    def preview(self, source_name: str, path: Path | str, limit: int = 10) -> list[RawPollImport]:
        """Load a file and return the first parsed rows without inserting."""
        source = get_source(source_name)
        resolved_path = self._validated_path(path)
        return source.load(resolved_path)[:limit]

    def run(
        self,
        source_name: str,
        path: Path | str,
        clean: bool = False,
        dry_run: bool = False,
    ) -> ImportResult:
        """Import file rows into polls_raw."""
        source = get_source(source_name)
        resolved_path = self._validated_path(path)
        stats = ImportStats()

        try:
            rows = source.load(resolved_path)
        except Exception as exc:
            stats.errors = 1
            stats.error_messages.append(str(exc))
            return ImportResult(source=source_name, path=str(resolved_path), stats=stats)

        stats.parsed = len(rows)
        raw_polls = [row.to_raw_dict() for row in rows]
        stats.inserted, stats.skipped = insert_raw_polls(self.db, raw_polls, dry_run=dry_run)

        cleaning_stats = None
        if clean and not dry_run and stats.inserted:
            cleaning_stats = run_cleaning_pipeline(self.db)

        logger.info(
            "Import complete: source=%s path=%s parsed=%s inserted=%s skipped=%s",
            source_name,
            resolved_path,
            stats.parsed,
            stats.inserted,
            stats.skipped,
        )
        return ImportResult(
            source=source_name,
            path=str(resolved_path),
            stats=stats,
            cleaning_stats=cleaning_stats,
        )

    def _validated_path(self, path: Path | str) -> Path:
        resolved_path = self.resolve_path(path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Import file not found: {resolved_path}")
        if not resolved_path.is_file():
            raise ValueError(f"Import path is not a file: {resolved_path}")
        return resolved_path
