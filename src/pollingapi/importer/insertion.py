"""Insertion helpers for imported raw polls."""

from typing import Any

from sqlalchemy.orm import Session

from pollingapi.models import RawPoll

DEDUP_KEYS = (
    "publish_date",
    "survey_date_start",
    "survey_date_end",
    "respondents",
    "zeitraum",
    "parties",
    "institute_id",
    "provider",
    "tasker",
    "source",
    "scope",
    "election_id",
    "method_id",
    "worker",
    "survey_type",
)


def raw_poll_exists(db: Session, raw_dict: dict[str, Any]) -> bool:
    """Return True when an equivalent raw poll already exists."""
    query = db.query(RawPoll)
    for key in DEDUP_KEYS:
        column = getattr(RawPoll, key)
        value = raw_dict.get(key)
        query = query.filter(column.is_(None)) if value is None else query.filter(column == value)
    return query.first() is not None


def insert_raw_polls(
    db: Session,
    raw_polls: list[dict[str, Any]],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Insert raw poll dictionaries, skipping duplicates."""
    inserted = 0
    skipped = 0
    seen_keys: set[tuple[Any, ...]] = set()

    for raw_dict in raw_polls:
        dedup_key = tuple(raw_dict.get(key) for key in DEDUP_KEYS)
        if dedup_key in seen_keys or raw_poll_exists(db, raw_dict):
            skipped += 1
            continue
        seen_keys.add(dedup_key)
        db.add(RawPoll(**raw_dict))
        inserted += 1

    if dry_run:
        db.rollback()
    elif inserted:
        db.commit()

    return inserted, skipped
