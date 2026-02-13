"""Runtime context for scraper execution."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pollingapi.core import PROJECT_ROOT


@dataclass(frozen=True)
class RunContext:
    """Shared runtime context for scrapers."""

    project_root: Path
    today_str: str
    debug: bool = False

    @classmethod
    def for_project(cls, project_root: Path = PROJECT_ROOT, debug: bool = False) -> "RunContext":
        """Create a context for the project."""
        return cls(
            project_root=project_root,
            today_str=datetime.now().strftime("%Y-%m-%d"),
            debug=debug,
        )
