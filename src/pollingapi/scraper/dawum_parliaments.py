"""Map DAWUM Parliament_ID values to canonical poll scope / election_id."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pollingapi.cleaner.transforms.references import normalized_scope, resolve_state
from pollingapi.scraper.datamodel import ElectionScope, GermanState

PARLIAMENTS_JSON = Path(__file__).resolve().parents[3] / "json" / "parliaments.json"


@dataclass(frozen=True)
class DawumParliamentMapping:
    """Canonical scope + election_id for a DAWUM parliament row."""

    scope: str
    election_id: str
    parliament_id: str
    shortcut: str | None = None


class UnknownDawumParliamentError(ValueError):
    """Raised when a DAWUM parliament cannot be mapped safely."""


@lru_cache(maxsize=1)
def _parliament_catalog() -> dict[str, dict]:
    if not PARLIAMENTS_JSON.exists():
        return {}
    raw = json.loads(PARLIAMENTS_JSON.read_text(encoding="utf-8"))
    return {str(key): value for key, value in raw.items() if isinstance(value, dict)}


def _election_id_for(state: GermanState, election_name: str | None) -> str:
    text = (election_name or "").lower()
    if "europa" in text:
        return ElectionScope.EU_WAHLEN.value
    if state in {GermanState.BUND, GermanState.OST, GermanState.WEST}:
        return ElectionScope.BUNDESTAGSWAHL.value
    return ElectionScope.LANDTAGSWAHL.value


def _state_from_labels(*labels: str | None) -> GermanState | None:
    """Resolve labels to a state, ignoring bare fallbacks to Bund."""
    for label in labels:
        if not label or not str(label).strip():
            continue
        text = str(label).strip()
        state = resolve_state(text)
        # resolve_state defaults unknown text to Bund — only accept that when
        # the label itself clearly refers to the federal level / EU.
        lowered = text.lower().strip()
        federalish = lowered in {
            "eu",
            "bund",
            "federal",
            "deutschland",
            "europawahl",
            "bundestag",
            "bundestagswahl",
        } or any(
            token in lowered
            for token in (
                "bundestag",
                "federal",
                "deutschland",
                "europa",
                "europäisch",
                "europaeisch",
            )
        )
        if state is GermanState.BUND and not federalish:
            continue
        return state
    return None


def map_dawum_parliament(
    parliament_id: str | int | None,
    *,
    shortcut: str | None = None,
    election: str | None = None,
) -> DawumParliamentMapping:
    """Map a DAWUM parliament to cleaned-poll scope and election_id.

    Prefers ``json/parliaments.json`` (stable IDs + aliases). Falls back to the
    live Shortcut/Election labels from the DAWUM dump. Never silently defaults
    an unrecognized Landtag parliament to federal.
    """
    pid = "" if parliament_id is None else str(parliament_id).strip()
    catalog = _parliament_catalog()
    entry = catalog.get(pid) if pid else None

    labels: list[str | None] = []
    election_name = election
    if entry:
        aliases = entry.get("Aliases") or []
        labels.extend(str(a) for a in aliases if a)
        labels.append(entry.get("Shortcut"))
        labels.append(entry.get("Name"))
        election_name = election_name or entry.get("Election")
        labels.append(election_name)
    labels.extend([shortcut, election])

    state = _state_from_labels(*labels)
    if state is None:
        raise UnknownDawumParliamentError(
            f"Cannot map DAWUM parliament_id={pid!r} shortcut={shortcut!r} "
            f"election={election!r} without risking a wrong federal assignment"
        )

    # Canonical API scopes: federal / be / nrw / …
    scope = "federal" if state is GermanState.BUND else normalized_scope(state.name)

    return DawumParliamentMapping(
        scope=scope,
        election_id=_election_id_for(state, election_name),
        parliament_id=pid,
        shortcut=(entry or {}).get("Shortcut") or shortcut,
    )


def clear_parliament_catalog_cache() -> None:
    """Test helper to reload parliaments.json."""
    _parliament_catalog.cache_clear()
