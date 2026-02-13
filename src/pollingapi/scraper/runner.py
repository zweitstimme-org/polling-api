"""Scraper runner to orchestrate all scraper workers."""

import importlib
from pathlib import Path

import typer
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.scraper.config import ScraperConfig, ScraperRegistry
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.dawum import DawumScraper


class ScraperRunner:
    """Runner to orchestrate scraper workers."""

    def __init__(
        self,
        db: Session,
        context: RunContext | None = None,
        dry_run: bool = False,
    ):
        """Initialize runner with database session."""
        self.db = db
        self.context = context or RunContext.for_project()
        self.dry_run = dry_run
        self.logger = get_logger("runner")
        self.workers_dir = Path(__file__).parent / "workers"

    def _discover_html_workers(self) -> list[tuple[str, ScraperConfig, type]]:
        """Discover HTML-based workers from sites_bund, sites_land and sites_eu."""
        discovered = []

        # Discover federal workers
        bund_dir = self.workers_dir / "sites_bund"
        if bund_dir.exists():
            for file in bund_dir.glob("*.py"):
                if file.name.startswith("_"):
                    continue
                try:
                    module_name = f"pollingapi.scraper.workers.sites_bund.{file.stem}"
                    module = importlib.import_module(module_name)
                    if hasattr(module, "get_config"):
                        config = module.get_config()
                        scraper_class = ScraperRegistry.get(config.type)
                        if scraper_class:
                            discovered.append((file.stem, config, scraper_class))
                        else:
                            self.logger.warning(
                                f"No scraper class registered for type: {config.type}"
                            )
                except Exception as e:
                    self.logger.warning(f"Failed to load worker {file.stem}: {e}")

        # Discover state workers
        land_dir = self.workers_dir / "sites_land"
        if land_dir.exists():
            for file in land_dir.glob("*.py"):
                if file.name.startswith("_"):
                    continue
                try:
                    module_name = f"pollingapi.scraper.workers.sites_land.{file.stem}"
                    module = importlib.import_module(module_name)
                    if hasattr(module, "get_config"):
                        config = module.get_config()
                        scraper_class = ScraperRegistry.get(config.type)
                        if scraper_class:
                            discovered.append((file.stem, config, scraper_class))
                        else:
                            self.logger.warning(
                                f"No scraper class registered for type: {config.type}"
                            )
                except Exception as e:
                    self.logger.warning(f"Failed to load worker {file.stem}: {e}")

        # Discover EU workers
        eu_dir = self.workers_dir / "sites_eu"
        if eu_dir.exists():
            for file in eu_dir.glob("*.py"):
                if file.name.startswith("_"):
                    continue
                try:
                    module_name = f"pollingapi.scraper.workers.sites_eu.{file.stem}"
                    module = importlib.import_module(module_name)
                    if hasattr(module, "get_config"):
                        config = module.get_config()
                        scraper_class = ScraperRegistry.get(config.type)
                        if scraper_class:
                            discovered.append((file.stem, config, scraper_class))
                        else:
                            self.logger.warning(
                                f"No scraper class registered for type: {config.type}"
                            )
                except Exception as e:
                    self.logger.warning(f"Failed to load worker {file.stem}: {e}")

        return discovered

    def _discover_all_workers(self) -> list[tuple[str, ScraperConfig, type]]:
        """Discover all workers."""
        workers = self._discover_html_workers()
        return workers

    def run_all(self, include_dawum: bool = True) -> dict[str, int | str]:
        """Run all scrapers and return summary.

        Args:
            include_dawum: Whether to include DAWUM API scraper

        Returns:
            Dictionary mapping worker names to inserted counts
        """
        results = {}

        # Get HTML workers
        html_workers = self._discover_html_workers()
        self.logger.info(f"Discovered {len(html_workers)} HTML workers")

        # Run HTML-based workers
        for _name, config, scraper_class in html_workers:
            try:
                typer.echo(f"Running {config.worker_name}...")
                scraper = scraper_class(config, self.db, context=self.context, dry_run=self.dry_run)
                count = scraper.run()
                results[config.worker_name] = count
                typer.echo(f"  ✓ {config.worker_name}: {count} polls")
            except Exception as e:
                self.logger.error(f"Error running {config.worker_name}: {e}")
                results[config.worker_name] = f"error: {e}"
                typer.echo(f"  ✗ {config.worker_name}: error - {e}")

        # Run DAWUM scraper if requested
        if include_dawum:
            try:
                typer.echo("Running DAWUM API scraper...")
                dawum = DawumScraper(self.db, context=self.context, dry_run=self.dry_run)
                count = dawum.run()
                results["dawum"] = count
                typer.echo(f"  ✓ dawum: {count} polls")
            except Exception as e:
                self.logger.error(f"Error running DAWUM: {e}")
                results["dawum"] = f"error: {e}"
                typer.echo(f"  ✗ dawum: error - {e}")

        return results

    def run_worker(self, worker_name: str) -> int:
        """Run a specific worker by name.

        Args:
            worker_name: Name of the worker to run (e.g., 'forsa', 'bayern', 'dawum')

        Returns:
            Number of polls inserted

        Raises:
            ValueError: If worker not found
        """
        # Check for DAWUM first
        if worker_name.lower() == "dawum":
            dawum = DawumScraper(self.db, context=self.context, dry_run=self.dry_run)
            return dawum.run()

        # Otherwise search HTML workers
        html_workers = self._discover_html_workers()
        for _name, config, scraper_class in html_workers:
            if config.worker_name == worker_name:
                scraper = scraper_class(config, self.db, context=self.context, dry_run=self.dry_run)
                return scraper.run()

        raise ValueError(f"Worker '{worker_name}' not found")

    def list_workers(self, include_dawum: bool = True) -> list[str]:
        """List all available workers including DAWUM."""
        workers = self._discover_all_workers()
        worker_names = [config.worker_name for _, config, _ in workers]
        if include_dawum:
            worker_names.append("dawum")
        return sorted(worker_names)
