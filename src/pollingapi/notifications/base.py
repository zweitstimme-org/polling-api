"""Base classes for the observability / notification layer.

All notification backends implement BaseNotifier.notify(result).
New services (Slack, email, Telegram, …) only need to subclass BaseNotifier
and register themselves with the NotificationManager — no changes to the
pipeline code are required.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScraperRunResult:
    """Per-worker scraper outcome."""

    worker_name: str
    polls_inserted: int = 0
    success: bool = True
    error: str | None = None


@dataclass
class PipelineRunResult:
    """Full summary of a single pipeline:run execution.

    Passed to every registered notifier at the end of the run.
    """

    # ------------------------------------------------------------------ meta
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None  # top-level failure message

    # ------------------------------------------------------------------ scraper
    scrapers_run: int = 0
    scrapers_succeeded: int = 0
    scrapers_failed: int = 0
    total_scraped_polls: int = 0
    scraper_errors: dict[str, str] = field(default_factory=dict)  # worker → error

    # ------------------------------------------------------------------ ETL cleaner
    etl_processed: int = 0
    etl_created: int = 0
    etl_updated: int = 0
    etl_skipped: int = 0
    etl_errors: int = 0

    # ------------------------------------------------------------------ export
    export_polls: int = 0
    export_poll_results: int = 0
    export_raw_polls: int = 0

    # ------------------------------------------------------------------ archive (optional)
    archive_created: bool = False
    archive_size_mb: float | None = None

    @property
    def duration_seconds(self) -> float:
        """Wall-clock duration of the run in seconds."""
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def duration_human(self) -> str:
        """Human-readable duration string, e.g. '1m 23s'."""
        total = int(self.duration_seconds)
        minutes, seconds = divmod(total, 60)
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"


class BaseNotifier(ABC):
    """Abstract base for all notification backends.

    Subclass this and implement :meth:`notify`.  The method should never
    raise — it must handle its own exceptions internally and log them.
    """

    @abstractmethod
    def notify(self, result: PipelineRunResult) -> None:
        """Send a run-summary notification.

        Args:
            result: The completed pipeline run result.
        """
        ...

    def is_configured(self) -> bool:
        """Return True if this notifier has the credentials / config it needs.

        Default implementation always returns True.  Override when your
        notifier requires external configuration (URLs, tokens, …).
        """
        return True
