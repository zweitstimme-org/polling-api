"""Insertion helpers: convert scraper poll models to polls_raw dict."""

import json
from datetime import datetime

from pollingapi.scraper.datamodel import BundElectionPoll, LandElectionPoll, PartyResult

ScraperPoll = BundElectionPoll | LandElectionPoll


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def poll_to_raw_dict(
    poll: ScraperPoll,
    survey_date_start: str | None = None,
    survey_date_end: str | None = None,
    provider: str | None = None,
    source: str | None = None,
    election_id: str | None = None,
    method_id: str | None = None,
    pipeline_run_id: str | None = None,
    survey_type: str | None = None,
) -> dict:
    """Convert scraper poll model to polls_raw dict for database insertion.
    Args:
        poll: The scraper poll model to convert.
        survey_date_start: Optional survey start date string.
        survey_date_end: Optional survey end date string.
        provider: Override for data source (defaults to poll.data_source).
        source: Override for source type (defaults to "html_scraper").
        election_id: Override for election type (defaults to poll.scope).
        method_id: Override for survey method (defaults to "99").
        pipeline_run_id: Optional pipeline run ID for traceability.
        survey_type: Optional parameter on forecast or poll
    Returns:
        Dictionary matching polls_raw table columns.
    """
    parties_dict = {p.name: p.value for p in poll.results}
    return {
        "publish_date": poll.datum,
        "survey_date_start": survey_date_start,
        "survey_date_end": survey_date_end,
        "respondents": poll.befragte,
        "zeitraum": poll.zeitraum,
        "parties": json.dumps(parties_dict, sort_keys=True),
        "institute_id": poll.institut,
        "provider": provider or poll.data_source,
        "tasker": poll.auftraggeber,
        "source": source or "html_scraper",
        "scope": poll.state,
        "election_id": election_id or poll.scope,
        "method_id": method_id or "99",
        "date_downloaded": poll.scraped_at.isoformat(),
        "worker": poll.worker,
        "survey_type": survey_type,
        "pipeline_run_id": pipeline_run_id,
    }


def raw_dict_to_poll(data: dict) -> BundElectionPoll:
    """Convert polls_raw dict back to BundElectionPoll.
    Args:
        data: Dictionary from polls_raw table row.
    Returns:
        BundElectionPoll model instance.
    """
    parties_raw = data.get("parties")
    if isinstance(parties_raw, str):
        parties_dict = json.loads(parties_raw)
    elif isinstance(parties_raw, dict):
        parties_dict = parties_raw
    else:
        parties_dict = {}

    raw_scraped_at = data.get("date_downloaded") or data.get("scraped_at")
    if isinstance(raw_scraped_at, datetime):
        scraped_at = raw_scraped_at
    elif isinstance(raw_scraped_at, str):
        scraped_at = _coerce_datetime(raw_scraped_at)
    else:
        scraped_at = datetime.now()

    results = [PartyResult(name=name, value=str(value)) for name, value in parties_dict.items()]
    return BundElectionPoll(
        scraped_at=scraped_at,
        data_source=data.get("provider") or data.get("data_source", ""),
        worker=data.get("worker", ""),
        scope=data.get("election_id", ""),
        state=data.get("scope", ""),
        institut=data.get("institute_id", ""),
        auftraggeber=data.get("tasker"),
        datum=data.get("publish_date", ""),
        befragte=data.get("respondents", ""),
        zeitraum=data.get("zeitraum", ""),
        survey_type=data.get("survey_type"),
        results=results,
    )
