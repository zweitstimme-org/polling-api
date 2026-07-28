import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.core import settings
from pollingapi.database import Base
from pollingapi.models import Party, Poll, PollResult, PollValidation
from pollingapi.services.export import ExportService


def _validation(poll_id: int) -> PollValidation:
    return PollValidation(
        poll_id=poll_id,
        validated_at=datetime(2024, 1, 1),
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
        details={},
    )


def test_export_writes_public_default_and_all_cleaned_dump(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(settings, "export_dir", tmp_path)

    session.add(Party(key="SPD", name="SPD", short_name="SPD"))
    session.add_all(
        [
            Poll(
                id=1,
                public_id="C00000001",
                publish_date=date(2024, 1, 1),
                is_public=True,
            ),
            Poll(
                id=2,
                public_id="C00000002",
                publish_date=date(2024, 1, 2),
                is_public=False,
                public_exclusion_reason="matched_secondary_provider",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            PollResult(poll_id=1, party_key="SPD", percentage=20),
            PollResult(poll_id=2, party_key="SPD", percentage=21),
            _validation(1),
            _validation(2),
        ]
    )
    session.commit()

    counts = ExportService(session).export_all()

    public_polls = json.loads((tmp_path / "polls.json").read_text(encoding="utf-8"))
    all_cleaned_polls = json.loads(
        (tmp_path / "all_cleaned_polls.json").read_text(encoding="utf-8")
    )
    public_results = json.loads((tmp_path / "poll_results.json").read_text(encoding="utf-8"))
    all_cleaned_results = json.loads(
        (tmp_path / "all_cleaned_poll_results.json").read_text(encoding="utf-8")
    )

    assert counts["polls"] == 1
    assert counts["all_cleaned_polls"] == 2
    assert [row["public_id"] for row in public_polls] == ["C00000001"]
    assert {row["public_id"] for row in all_cleaned_polls} == {"C00000001", "C00000002"}
    assert [row["poll_public_id"] for row in public_results] == ["C00000001"]
    assert {row["poll_public_id"] for row in all_cleaned_results} == {
        "C00000001",
        "C00000002",
    }


def test_archive_stage_includes_latest_report(tmp_path, monkeypatch):
    from pollingapi.cli import _stage_archive_bundle

    export_dir = tmp_path / "export"
    report_dir = tmp_path / "reports"
    project_dir = tmp_path / "project"
    export_dir.mkdir()
    report_dir.mkdir()
    (project_dir / "json").mkdir(parents=True)
    (export_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (report_dir / "pollingapi-report-latest.pdf").write_bytes(b"%PDF-1.7\n")
    (project_dir / "validation.toml").write_text("", encoding="utf-8")
    (project_dir / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "export_dir", export_dir)
    monkeypatch.setattr(settings, "report_dir", report_dir)
    monkeypatch.setattr("pollingapi.cli.PROJECT_ROOT", project_dir)

    _stage_archive_bundle(tmp_path / "archive")

    assert (tmp_path / "archive" / "reports" / "pollingapi-report-latest.pdf").exists()
