"""PDF report generation for pollingAPI data runs."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import desc, extract, func
from sqlalchemy.orm import Session

from pollingapi.core import settings
from pollingapi.data_validation import ValidationReportService
from pollingapi.models import PipelineRun, Poll, PollValidation, Provider

LATEST_REPORT_NAME = "pollingapi-report-latest.pdf"


class ReportGenerationError(RuntimeError):
    """Raised when the PDF report cannot be generated."""


@dataclass(frozen=True)
class YearSourceSummary:
    """Poll and source summary for one year."""

    year: int
    total_polls: int
    validated_polls: int
    primary_provider: str
    primary_provider_polls: int
    primary_source: str
    primary_source_polls: int


class ReportService:
    """Build a compact Typst PDF report from persisted polling data."""

    def __init__(self, db: Session, report_dir: Path | None = None):
        """Initialize the report service."""
        self.db = db
        self.report_dir = report_dir or settings.report_dir

    def generate(self, run_id: str | None = None) -> Path:
        """Generate a PDF report and return the timestamped report path.

        Args:
            run_id: Optional pipeline run id to connect the report to a run.

        Returns:
            Path to the timestamped report PDF.
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)
        payload = self._build_payload(run_id=run_id)
        source_path = self.report_dir / f"{payload['file_stem']}.typ"
        output_path = self.report_dir / f"{payload['file_stem']}.pdf"
        latest_path = self.latest_report_path()

        source_path.write_text(_render_typst(payload), encoding="utf-8")
        try:
            import typst

            typst.compile(source_path, output=output_path, root=self.report_dir)
        except Exception as exc:
            raise ReportGenerationError(f"Failed to generate report PDF: {exc}") from exc

        latest_path.write_bytes(output_path.read_bytes())
        return output_path

    def latest_report_path(self) -> Path:
        """Return the path of the latest report PDF."""
        return self.report_dir / LATEST_REPORT_NAME

    def _build_payload(self, run_id: str | None) -> dict[str, Any]:
        generated_at = dt.datetime.now(dt.UTC)
        run = self._get_run(run_id)
        validation = ValidationReportService(self.db).build_report(top_n=5)
        year_summaries = self._year_summaries()

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
                    "primary_provider_polls": item.primary_provider_polls,
                    "primary_source": item.primary_source,
                    "primary_source_polls": item.primary_source_polls,
                }
                for item in year_summaries
            ],
        }

    def _get_run(self, run_id: str | None) -> PipelineRun | None:
        query = self.db.query(PipelineRun)
        if run_id:
            return query.filter(PipelineRun.run_id == run_id).first()
        return query.order_by(desc(PipelineRun.finished_at)).first()

    def _year_summaries(self) -> list[YearSourceSummary]:
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
        providers = self._top_values_by_year(Provider.name, join_provider=True)
        sources = self._top_values_by_year(Poll.source)

        summaries = []
        for year in sorted(poll_counts, reverse=True):
            provider_name, provider_count = providers.get(year, ("unknown", 0))
            source_name, source_count = sources.get(year, ("unknown", 0))
            summaries.append(
                YearSourceSummary(
                    year=year,
                    total_polls=poll_counts[year],
                    validated_polls=validated_counts.get(year, 0),
                    primary_provider=provider_name,
                    primary_provider_polls=provider_count,
                    primary_source=source_name,
                    primary_source_polls=source_count,
                )
            )
        return summaries

    def _top_values_by_year(
        self,
        value_column: Any,
        join_provider: bool = False,
    ) -> dict[int, tuple[str, int]]:
        query = self.db.query(
            extract("year", Poll.publish_date).label("year"),
            value_column.label("value"),
            func.count(Poll.id).label("count"),
        ).filter(Poll.publish_date.is_not(None))

        if join_provider:
            query = query.outerjoin(Provider, Poll.provider_id == Provider.id)

        rows = query.group_by("year", "value").all()
        top_by_year: dict[int, tuple[str, int]] = {}
        for year, value, count in rows:
            if year is None:
                continue
            year_key = int(year)
            label = str(value or "unknown")
            current = top_by_year.get(year_key)
            if current is None or count > current[1]:
                top_by_year[year_key] = (label, count)
        return top_by_year


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


def _render_typst(payload: dict[str, Any]) -> str:
    rows = "\n".join(_year_row(item) for item in payload["years"])
    check_rows = "\n".join(_check_row(item) for item in payload["checks"])
    failure_rows = "\n".join(_failure_row(item) for item in payload["top_failures"])
    if not failure_rows:
        failure_rows = "No failed validation checks."

    return f"""
#set document(title: {_typst_string(payload["title"])})
#set page(paper: "a4", margin: 18mm)
#set text(font: "Libertinus Serif", size: 10pt)
#show heading: set text(font: "Libertinus Serif")

= {_typst_inline(payload["title"])}

Generated: {_typst_inline(payload["generated_at"])} \
API version: {_typst_inline(payload["api_version"])}

== Pipeline Run

#table(
  columns: (35%, 65%),
  inset: 6pt,
  stroke: 0.5pt + gray,
  [Run ID], [{_typst_inline(payload["run"]["run_id"])}],
  [Success], [{_typst_inline(payload["run"]["success"])}],
  [Started], [{_typst_inline(payload["run"]["started_at"])}],
  [Finished], [{_typst_inline(payload["run"]["finished_at"])}],
  [Duration], [{_typst_inline(payload["run"]["duration"])}],
  [Scraped polls], [{payload["run"]["scraped"]}],
  [Created / updated], [{payload["run"]["created"]} / {payload["run"]["updated"]}],
  [ETL errors], [{payload["run"]["errors"]}],
)

== Data Quality Summary

#table(
  columns: (45%, 55%),
  inset: 6pt,
  stroke: 0.5pt + gray,
  [Status], [{_typst_inline(payload["totals"]["status"])}],
  [Total polls], [{payload["totals"]["polls"]}],
  [Validated polls], [{payload["totals"]["validated_polls"]}],
  [Valid polls], [{payload["totals"]["valid_polls"]} ({_typst_inline(payload["totals"]["valid_share"])})],
  [Invalid polls], [{payload["totals"]["invalid_polls"]}],
  [Warning polls], [{payload["totals"]["warning_polls"]}],
  [Latest validation], [{_typst_inline(payload["totals"]["latest_validated_at"])}],
)

== Primary Sources by Year

#table(
  columns: (12%, 15%, 17%, 22%, 14%, 20%),
  inset: 5pt,
  stroke: 0.4pt + gray,
  table.header([Year], [Polls], [Validated], [Primary provider], [Provider polls], [Primary source]),
{rows}
)

== Validation Checks

#table(
  columns: (45%, 18%, 18%, 19%),
  inset: 5pt,
  stroke: 0.4pt + gray,
  table.header([Check], [Passed], [Failed], [Pass share]),
{check_rows}
)

== Top Failures

{failure_rows}
""".lstrip()


def _year_row(item: dict[str, Any]) -> str:
    source = f"{item['primary_source']} ({item['primary_source_polls']})"
    return (
        f"  [{item['year']}], [{item['total_polls']}], [{item['validated_polls']}], "
        f"[{_typst_inline(item['primary_provider'])}], [{item['primary_provider_polls']}], "
        f"[{_typst_inline(source)}],"
    )


def _check_row(item: dict[str, Any]) -> str:
    return (
        f"  [{_typst_inline(item['name'])}], [{item['passed']}], "
        f"[{item['failed']}], [{_typst_inline(item['pass_share'])}],"
    )


def _failure_row(item: dict[str, Any]) -> str:
    return f"- {_typst_inline(item['name'])}: {item['failed']}"


def _typst_inline(value: object) -> str:
    return f"#raw({_typst_string(str(value))})"


def _typst_string(value: str) -> str:
    return json.dumps(value)


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
