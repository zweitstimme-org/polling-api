"""Deterministic fingerprints for cleaned polls."""

from __future__ import annotations

import hashlib
import json
from datetime import date


def _date_to_str(value: date | None) -> str | None:
    return value.isoformat() if value else None


def build_poll_fingerprint(
    *,
    publish_date: date | None,
    survey_date_start: date | None,
    survey_date_end: date | None,
    respondents: int | None,
    institute_key: str | None,
    provider_name: str | None,
    source: str | None,
    method_key: str | None,
    election_key: str | None,
    scope: str | None,
    results: dict[str, float],
) -> str:
    """Return a stable SHA-256 hash for a normalized cleaned poll."""
    payload = {
        "publish_date": _date_to_str(publish_date),
        "survey_date_start": _date_to_str(survey_date_start),
        "survey_date_end": _date_to_str(survey_date_end),
        "respondents": respondents,
        "institute_key": institute_key,
        "provider_name": provider_name,
        "source": source,
        "method_key": method_key,
        "election_key": election_key,
        "scope": scope,
        "results": {key: round(float(value), 3) for key, value in sorted(results.items())},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
