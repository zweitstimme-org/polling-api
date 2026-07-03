"""Content fingerprints for raw poll deduplication."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

FINGERPRINT_FIELDS = (
    "scope",
    "election_id",
    "publish_year",
    "publish_week",
    "institute_id",
    "survey_type",
    "union_share",
    "spd_share",
)

UNION_PARTY_NAMES = {"cdu/csu", "union", "cdu", "csu"}
SPD_PARTY_NAMES = {"spd"}


def build_content_fingerprint(raw_dict: dict[str, Any]) -> str:
    """Build the canonical content string used for raw poll hashes.

    The fingerprint intentionally excludes provider, source, worker, respondents,
    tasker, and download time so the same poll can be detected across sources.
    """
    year, week = _year_week(raw_dict.get("publish_date"))
    parties = _load_parties(raw_dict.get("parties"))
    parts = {
        "scope": _normalize_text(raw_dict.get("scope")),
        "election_id": _normalize_text(raw_dict.get("election_id")),
        "publish_year": str(year) if year is not None else "",
        "publish_week": f"{week:02d}" if week is not None else "",
        "institute_id": _normalize_text(raw_dict.get("institute_id")),
        "survey_type": _normalize_text(raw_dict.get("survey_type")),
        "union_share": _party_share(parties, UNION_PARTY_NAMES),
        "spd_share": _party_share(parties, SPD_PARTY_NAMES),
    }
    return "|".join(f"{key}={parts[key]}" for key in FINGERPRINT_FIELDS)


def build_content_hash(raw_dict: dict[str, Any]) -> str:
    """Build a SHA-256 hash from the canonical raw poll fingerprint."""
    fingerprint = build_content_fingerprint(raw_dict)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _year_week(value: Any) -> tuple[int | None, int | None]:
    parsed = _parse_date(value)
    if parsed is None:
        return None, None
    calendar = parsed.isocalendar()
    return calendar.year, calendar.week


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(0))
        except ValueError:
            return None

    german_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if german_match:
        day, month, year = (int(part) for part in german_match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def _load_parties(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _party_share(parties: dict[str, Any], accepted_names: set[str]) -> str:
    for name, value in parties.items():
        normalized_name = _normalize_party_name(name)
        if normalized_name in accepted_names:
            return _normalize_share(value)
    return ""


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def _normalize_party_name(value: Any) -> str:
    text = _normalize_text(value)
    text = text.replace("ü", "ue").replace("ö", "oe").replace("ä", "ae").replace("ß", "ss")
    return text


def _normalize_share(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("%", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return ""
    number = float(match.group(0))
    return f"{number:.1f}"
