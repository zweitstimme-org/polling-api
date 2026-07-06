import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path

import typer
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.models import RawPoll
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.dawum import DawumScraper


@dataclass(frozen=True)
class WorkerEntry:
    worker_name: str
    scraper_class: type
    module_name: str


class ScraperRunner:
    """Runner to orchestrate scraper workers."""

    def __init__(
        self,
        db: Session,
        context: RunContext | None = None,
        dry_run: bool = False,
    ):
        self.db = db
        self.context = context or RunContext.for_project()
        self.dry_run = dry_run
        self.logger = get_logger("runner")
        self.workers_dir = Path(__file__).parent / "workers"
        self.zero_poll_workers: list[str] = []

    def _discover_worker_modules(self) -> list[str]:
        """Discover worker modules in bund + land only."""
        module_names: list[str] = []
        for scope in ("sites_bund", "sites_land"):
            scope_dir = self.workers_dir / scope
            if not scope_dir.exists():
                continue
            for file in sorted(scope_dir.glob("*.py")):
                if file.name.startswith("_"):
                    continue
                module_names.append(f"pollingapi.scraper.workers.{scope}.{file.stem}")
        return module_names

    def _is_concrete_worker_class(self, cls: type, module_name: str) -> bool:
        """Filter concrete worker classes (exclude bases/imported classes)."""
        return (
            cls.__module__ == module_name
            and cls.__name__.endswith("Scraper")
            and not cls.__name__.endswith("BaseScraper")
            and bool(getattr(cls, "WORKER", ""))
            and bool(getattr(cls, "URL", ""))
            and hasattr(cls, "run")
        )

    def _discover_html_workers(self) -> list[WorkerEntry]:
        """Discover all class-based HTML workers from bund + land."""
        discovered: list[WorkerEntry] = []
        seen_workers: set[str] = set()
        for module_name in self._discover_worker_modules():
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                self.logger.warning(f"Failed to import module {module_name}: {exc}")
                continue
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if not self._is_concrete_worker_class(cls, module_name):
                    continue
                worker_name = getattr(cls, "WORKER", "").strip()
                if worker_name in seen_workers:
                    self.logger.warning(
                        f"Duplicate worker '{worker_name}' in {module_name}; skipping duplicate."
                    )
                    continue
                discovered.append(
                    WorkerEntry(
                        worker_name=worker_name,
                        scraper_class=cls,
                        module_name=module_name,
                    )
                )
                seen_workers.add(worker_name)
        discovered.sort(key=lambda x: x.worker_name)
        return discovered

    def _instantiate_worker(self, scraper_class: type):
        """Instantiate worker with supported constructor signature."""
        init_sig = inspect.signature(scraper_class.__init__)
        if "dry_run" in init_sig.parameters:
            return scraper_class(db=self.db, context=self.context, dry_run=self.dry_run)
        return scraper_class(db=self.db, context=self.context)

    def _has_existing_raw_polls(self, worker_name: str) -> bool:
        """Return True if this worker has ever inserted raw polls before."""
        return self.db.query(RawPoll.id).filter(RawPoll.worker == worker_name).first() is not None

    def _record_zero_poll_warning(self, worker_name: str, polls_found: int | None) -> None:
        if polls_found != 0 or not self._has_existing_raw_polls(worker_name):
            return
        if worker_name not in self.zero_poll_workers:
            self.zero_poll_workers.append(worker_name)
        self.logger.warning(
            f"Worker {worker_name} found no polls, but previous raw polls exist for this worker"
        )

    def _run_scraper(self, worker_name: str, scraper) -> int:
        """Run a scraper and record whether it found zero polls.

        HTML workers share fetch/save_snapshot/parse/insert methods, so running
        that flow here lets the runner observe parsed poll count without changing
        every worker class.
        """
        if all(hasattr(scraper, attr) for attr in ("fetch", "save_snapshot", "parse", "insert")):
            html = scraper.fetch()
            scraper.save_snapshot(html)
            polls = scraper.parse(html)
            polls_found = len(polls)
            self._record_zero_poll_warning(worker_name, polls_found)
            return scraper.insert(polls)

        count = scraper.run()
        self._record_zero_poll_warning(worker_name, getattr(scraper, "last_polls_found", None))
        return count

    @staticmethod
    def _is_current_worker(entry: WorkerEntry) -> bool:
        """Return True when worker class name contains 'current'."""
        return "current" in entry.scraper_class.__name__.lower()

    def run_all(
        self,
        include_dawum: bool = True,
        current_only: bool = False,
    ) -> dict[str, int | str]:
        """Run discovered workers and optional DAWUM."""
        results: dict[str, int | str] = {}
        self.zero_poll_workers = []
        workers = self._discover_html_workers()
        if current_only:
            workers = [entry for entry in workers if self._is_current_worker(entry)]
        self.logger.info(f"Discovered {len(workers)} HTML workers")
        for entry in workers:
            try:
                typer.echo(f"Running {entry.worker_name}...")
                scraper = self._instantiate_worker(entry.scraper_class)
                count = self._run_scraper(entry.worker_name, scraper)
                results[entry.worker_name] = count
                typer.echo(f"  ✓ {entry.worker_name}: {count} polls")
            except Exception as exc:
                self.logger.error(f"Error running {entry.worker_name}: {exc}")
                results[entry.worker_name] = f"error: {exc}"
                typer.echo(f"  ✗ {entry.worker_name}: error - {exc}")
        if include_dawum:
            try:
                typer.echo("Running DAWUM API scraper...")
                dawum = DawumScraper(self.db, context=self.context, dry_run=self.dry_run)
                count = self._run_scraper("dawum", dawum)
                results["dawum"] = count
                typer.echo(f"  ✓ dawum: {count} polls")
            except Exception as exc:
                self.logger.error(f"Error running DAWUM: {exc}")
                results["dawum"] = f"error: {exc}"
                typer.echo(f"  ✗ dawum: error - {exc}")
        return results

    def run_worker(self, worker_name: str) -> int:
        """Run a specific worker by WORKER name."""
        if worker_name.lower() == "dawum":
            dawum = DawumScraper(self.db, context=self.context, dry_run=self.dry_run)
            self.zero_poll_workers = []
            return self._run_scraper("dawum", dawum)
        workers = self._discover_html_workers()
        for entry in workers:
            if entry.worker_name == worker_name:
                scraper = self._instantiate_worker(entry.scraper_class)
                self.zero_poll_workers = []
                return self._run_scraper(entry.worker_name, scraper)
        raise ValueError(f"Worker '{worker_name}' not found")

    def list_workers(self, include_dawum: bool = True) -> list[str]:
        """List all available worker names."""
        names = [entry.worker_name for entry in self._discover_html_workers()]
        if include_dawum:
            names.append("dawum")
        return sorted(names)
