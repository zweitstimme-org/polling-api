"""PDF report generation for pollingAPI data runs."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import toml
from sqlalchemy import desc, extract, func
from sqlalchemy.orm import Session

from pollingapi.core import PROJECT_ROOT, settings
from pollingapi.data_validation import ValidationReportService
from pollingapi.models import PipelineRun, Poll, PollValidation, Provider

LATEST_REPORT_NAME = "pollingapi-report-latest.pdf"
REPORT_CONFIG_PATH = PROJECT_ROOT / "report.toml"


class ReportGenerationError(RuntimeError):
    """Raised when the PDF report cannot be generated."""


@dataclass(frozen=True)
class YearSourceSummary:
    """Poll and source summary for one year."""

    year: int
    total_polls: int
    validated_polls: int
    primary_provider: str
    primary_source: str
    primary_polls: int


class ReportService:
    """Build a compact Typst PDF report from persisted polling data."""

    def __init__(
        self,
        db: Session,
        report_dir: Path | None = None,
        config_path: Path | None = None,
    ):
        """Initialize the report service."""
        self.db = db
        self.report_dir = report_dir or settings.report_dir
        self.config_path = config_path or REPORT_CONFIG_PATH

    def generate(self, run_id: str | None = None) -> Path:
        """Generate a PDF report and return the timestamped report path.

        Args:
            run_id: Optional pipeline run id to connect the report to a run.

        Returns:
            Path to the timestamped report PDF.
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)
        payload = self._build_payload(run_id=run_id)
        output_path = self.report_dir / f"{payload['file_stem']}.pdf"
        latest_path = self.latest_report_path()

        try:
            import typst

            typst.compile(
                self._template_path(),
                output=output_path,
                root=PROJECT_ROOT,
                sys_inputs={"report": json.dumps(payload)},
            )
        except Exception as exc:
            raise ReportGenerationError(f"Failed to generate report PDF: {exc}") from exc

        latest_path.write_bytes(output_path.read_bytes())
        return output_path

    def latest_report_path(self) -> Path:
        """Return the path of the latest report PDF."""
        return self.report_dir / LATEST_REPORT_NAME

    def _template_path(self) -> Path:
        return Path(str(files("pollingapi.templates").joinpath("report.typ")))

    def _build_payload(self, run_id: str | None) -> dict[str, Any]:
        generated_at = dt.datetime.now(dt.UTC)
        run = self._get_run(run_id)
        validation = ValidationReportService(self.db).build_report(top_n=5)
        config = self._load_config()
        year_summaries = self._year_summaries(config)

        connected_run_id = run.run_id if run else run_id
        file_stem = (
            f"pollingapi-report-{_slug(connected_run_id)}"
            if connected_run_id
            else f"pollingapi-report-{generated_at.strftime('%Y-%m-%d-%H-%M-%S')}"
        )

        return {
            "title": "Zweitstimme Polling API Report",
            "generated_at": _format_datetime(generated_at),
            "api_version": settings.api_version,
            "file_stem": file_stem,
            "run": _run_payload(run, connected_run_id),
            "totals": {
                "polls": self.db.query(Poll).count(),
                "validated_polls": self.db.query(PollValidation).count(),
                "valid_polls": validation.valid_polls,
                "invalid_polls": validation.invalid_polls,
                "warning_polls": validation.warning_polls,
                "valid_share": _format_percent(validation.valid_share),
                "status": validation.status,
                "latest_validated_at": _format_datetime(validation.latest_validated_at),
            },
            "checks": [
                {
                    "name": check.check,
                    "passed": check.passed,
                    "failed": check.failed,
                    "pass_share": _format_percent(check.pass_share),
                }
                for check in validation.checks
            ],
            "top_failures": [
                {"name": item.check, "failed": item.failed}
                for item in validation.top_failure_checks
            ],
            "years": [
                {
                    "year": item.year,
                    "total_polls": item.total_polls,
                    "validated_polls": item.validated_polls,
                    "primary_provider": item.primary_provider,
                    "primary_source": item.primary_source,
                    "primary_polls": item.primary_polls,
                }
                for item in year_summaries
            ],
        }

    def _get_run(self, run_id: str | None) -> PipelineRun | None:
        query = self.db.query(PipelineRun)
        if run_id:
            return query.filter(PipelineRun.run_id == run_id).first()
        return query.order_by(desc(PipelineRun.finished_at)).first()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        return toml.load(self.config_path)

    def _year_summaries(self, config: dict[str, Any]) -> list[YearSourceSummary]:
        poll_counts = {
            int(year): count
            for year, count in (
                self.db.query(extract("year", Poll.publish_date), func.count(Poll.id))
                .filter(Poll.publish_date.is_not(None))
                .group_by(extract("year", Poll.publish_date))
                .all()
            )
            if year is not None
        }
        validated_counts = {
            int(year): count
            for year, count in (
                self.db.query(extract("year", Poll.publish_date), func.count(PollValidation.id))
                .join(PollValidation, PollValidation.poll_id == Poll.id)
                .filter(Poll.publish_date.is_not(None))
                .group_by(extract("year", Poll.publish_date))
                .all()
            )
            if year is not None
        }

        summaries = []
        for year in sorted(poll_counts, reverse=True):
            provider_name, source_name = self._configured_primary_source(config, year)
            summaries.append(
                YearSourceSummary(
                    year=year,
                    total_polls=poll_counts[year],
                    validated_polls=validated_counts.get(year, 0),
                    primary_provider=provider_name,
                    primary_source=source_name,
                    primary_polls=self._primary_poll_count(year, provider_name, source_name),
                )
            )
        return summaries

    def _configured_primary_source(self, config: dict[str, Any], year: int) -> tuple[str, str]:
        primary_sources = config.get("primary_sources", {})
        defaults = primary_sources.get("default", {})
        years = primary_sources.get("years", {})
        year_config = years.get(str(year), {})
        provider = year_config.get("provider") or defaults.get("provider") or "not configured"
        source = year_config.get("source") or defaults.get("source") or "not configured"
        return str(provider), str(source)

    def _primary_poll_count(self, year: int, provider_name: str, source: str) -> int:
        query = (
            self.db.query(func.count(Poll.id))
            .outerjoin(Provider, Poll.provider_id == Provider.id)
            .filter(extract("year", Poll.publish_date) == year)
        )
        if provider_name != "not configured":
            query = query.filter(Provider.name == provider_name)
        if source != "not configured":
            query = query.filter(Poll.source == source)
        return int(query.scalar() or 0)


def _run_payload(run: PipelineRun | None, fallback_run_id: str | None) -> dict[str, Any]:
    if run is None:
        return {
            "run_id": fallback_run_id or "not connected",
            "success": "n/a",
            "started_at": "n/a",
            "finished_at": "n/a",
            "duration": "n/a",
            "scraped": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
        }
    return {
        "run_id": run.run_id,
        "success": "yes" if run.success else "no",
        "started_at": _format_datetime(run.started_at),
        "finished_at": _format_datetime(run.finished_at),
        "duration": f"{run.duration_seconds:.1f}s",
        "scraped": run.total_scraped_polls,
        "created": run.etl_created,
        "updated": run.etl_updated,
        "errors": run.etl_errors,
    }


def _format_datetime(value: dt.datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.isoformat(timespec="seconds")


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _slug(value: str | None) -> str:
    if not value:
        return "latest"
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
