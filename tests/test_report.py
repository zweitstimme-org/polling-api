"""Tests for PDF report generation."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.database import Base
from pollingapi.models import PipelineRun, Poll, PollValidation, Provider
from pollingapi.services.report import ReportService


def test_report_service_generates_run_linked_pdf(tmp_path) -> None:
    """Test report generation writes a run-linked PDF and latest copy."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    provider = Provider(id=1, name="Wahlrecht.de")
    poll = Poll(
        id=1,
        public_id="C00000001",
        publish_date=dt.date(2024, 6, 1),
        provider=provider,
        source="html_scraper",
        scope="federal",
    )
    validation = PollValidation(
        poll=poll,
        validated_at=dt.datetime(2024, 6, 2, 12, 0, 0),
        valid=True,
        error_count=0,
        warning_count=0,
        qc_party_percentage_range=True,
        qc_result_sum_check=True,
        qc_date_consistency=True,
        qc_respondents_plausible=True,
        qc_core_parties_present=True,
        qc_institute_result_jump=True,
        qc_scope_result_jump=True,
        details={"public_id": "C00000001"},
    )
    run = PipelineRun(
        run_id="test-run-1",
        started_at=dt.datetime(2024, 6, 2, 12, 0, 0),
        finished_at=dt.datetime(2024, 6, 2, 12, 1, 0),
        duration_seconds=60.0,
        success=True,
        total_scraped_polls=1,
        etl_created=1,
        etl_updated=0,
        etl_errors=0,
        validation_status="pass",
        validation_total_polls=1,
        validation_valid_polls=1,
        validation_invalid_polls=0,
        validation_warning_polls=0,
        validation_valid_share=1.0,
    )
    session.add_all([poll, validation, run])
    session.commit()
    config_path = tmp_path / "report.toml"
    config_path.write_text(
        """
[primary_sources.default]
provider = "Other"
source = "api"

[primary_sources.years."2024"]
provider = "Wahlrecht.de"
source = "html_scraper"
""".strip(),
        encoding="utf-8",
    )

    service = ReportService(session, tmp_path, config_path=config_path)
    payload = service._build_payload(run_id="test-run-1")
    report_path = service.generate(run_id="test-run-1")

    assert payload["years"][0]["primary_provider"] == "Wahlrecht.de"
    assert payload["years"][0]["primary_source"] == "html_scraper"
    assert payload["years"][0]["primary_polls"] == 1
    assert report_path.name == "pollingapi-report-test-run-1.pdf"
    assert report_path.read_bytes().startswith(b"%PDF")
    assert (tmp_path / "pollingapi-report-latest.pdf").read_bytes().startswith(b"%PDF")
