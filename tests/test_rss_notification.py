"""Tests for RSS notification output."""

from __future__ import annotations

import datetime as dt
from xml.etree import ElementTree as ET

from pollingapi.notifications import PipelineRunResult
from pollingapi.notifications.rss_notification import RssNotifier


def test_rss_notifier_writes_pipeline_summary_feed(tmp_path) -> None:
    feed_path = tmp_path / "notifications.xml"
    notifier = RssNotifier(feed_path=feed_path, title_prefix="pollingAPI", max_items=1)

    old = _result("old-run", dt.datetime(2026, 7, 29, 12, 0, 0))
    new = _result("new-run", dt.datetime(2026, 7, 30, 12, 0, 0))
    notifier.notify(old)
    notifier.notify(new)

    root = ET.parse(feed_path).getroot()
    channel = root.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == 1
    assert items[0].findtext("guid") == "new-run"
    assert items[0].findtext("title") == "[pollingAPI] Pipeline SUCCESS"
    description = items[0].findtext("description") or ""
    assert "--- Scraper ---" in description
    assert "--- ETL Cleaner ---" in description
    assert "--- Validation ---" in description
    assert "--- Export ---" in description


def _result(run_id: str, finished_at: dt.datetime) -> PipelineRunResult:
    return PipelineRunResult(
        run_id=run_id,
        started_at=finished_at - dt.timedelta(minutes=1),
        finished_at=finished_at,
        success=True,
        scrapers_run=2,
        scrapers_succeeded=2,
        total_scraped_polls=3,
        etl_processed=3,
        etl_created=2,
        etl_updated=1,
        validation_status="pass",
        validation_total_polls=3,
        validation_valid_polls=3,
        validation_valid_share=1.0,
        export_polls=3,
        export_poll_results=12,
        export_raw_polls=4,
    )
