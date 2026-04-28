"""JSON-based mappings for data cleaning.

This module provides mappings from the json/ directory files.
These mappings convert scraper output names to the canonical IDs defined in JSON.
"""

import json
import re
from functools import cache, lru_cache
from pathlib import Path


def _load_json(filename: str) -> dict:
    """Load JSON file from project root json/ directory."""
    json_dir = Path(__file__).parent.parent.parent.parent / "json"
    with open(json_dir / filename, encoding="utf-8") as f:
        return json.load(f)


@cache
def _load_json_cached(filename: str) -> dict:
    """Load JSON mapping file with process-local caching."""
    return _load_json(filename)


# ============================================================================
# Institute Mappings
# ============================================================================


@lru_cache(maxsize=1)
def _build_institute_lookup() -> dict[str, int]:
    """Build lookup: normalized name -> institute ID."""
    data = _load_json("institutes.json")
    lookup = {}

    for institute_id, info in data.items():
        id_int = int(institute_id)
        name = info.get("Name", "")

        # Map the canonical name
        if name:
            lookup[name.lower().strip()] = id_int
            # Also map without special chars
            simplified = re.sub(r"[^\w\s]", "", name.lower())
            lookup[simplified] = id_int

    variations = {
        "forschungsgruppewahlen": 6,
        "forschungsgruppe wahlen": 6,
        "forschungsgruppe-wahlen": 6,
        "forschungs-gruppewahlen": 6,
        "tnsinfratest": 1,
        "tns infratest": 1,
        "infratestpolitikforschung": 1,
        "infratestpolitik-forschung": 1,
        "infratest burke": 1,
        "ipos": 17,
    }
    lookup.update(variations)

    return lookup


def get_institute_name(institute_id: int, fallback: str | None = None) -> str:
    """Return canonical institute name for an ID."""
    if institute_id == 99:
        return "Unknown"
    data = _load_json_cached("institutes.json")
    item = data.get(str(institute_id))
    if item and item.get("Name"):
        return item["Name"]
    return fallback or "Unknown"


def map_institute(name: str) -> int:
    """Map institute name to ID.

    Args:
        name: Institute name from scraper (e.g., "Forsa", "INSA")

    Returns:
        Institute ID from JSON file, or 99 (Unknown) if not found
    """
    if not name:
        return 99

    lookup = _build_institute_lookup()

    # Try exact match first
    name_lower = name.lower().strip()
    if name_lower in lookup:
        return lookup[name_lower]

    # Try without special characters
    simplified = re.sub(r"[^\w\s]", "", name_lower)
    if simplified in lookup:
        return lookup[simplified]

    # Try partial match (for names like "Verian (Emnid)")
    for key, id_val in lookup.items():
        if key in name_lower or name_lower in key:
            return id_val

    return 99  # Unknown


# ============================================================================
# Party Mappings
# ============================================================================


@lru_cache(maxsize=1)
def _build_party_lookup() -> dict[str, int]:
    """Build lookup: normalized party name -> party ID."""
    data = _load_json("parties.json")
    lookup = {}

    for party_id, info in data.items():
        id_int = int(party_id)

        # Map by Shortcut (e.g., "AfD", "SPD")
        shortcut = info.get("Shortcut", "")
        if shortcut:
            lookup[shortcut.lower().strip()] = id_int

        # Map by Name (e.g., "Alternative für Deutschland")
        name = info.get("Name", "")
        if name:
            lookup[name.lower().strip()] = id_int

    return lookup


def map_party(name: str) -> int | None:
    """Map party name to ID.

    Args:
        name: Party name from scraper (e.g., "AfD", "CDU/CSU", "Grüne")

    Returns:
        Party ID from JSON file, or None if not found
    """
    if not name:
        return None

    lookup = _build_party_lookup()

    # Try exact match
    name_lower = name.lower().strip()
    if name_lower in lookup:
        return lookup[name_lower]

    # Try without special characters
    simplified = re.sub(r"[^\w\s]", "", name_lower)
    if simplified in lookup:
        return lookup[simplified]

    # Common variations
    variations = {
        "cdu": 1,
        "csu": 1,
        "cdu/csu": 1,
        "union": 1,
        "spd": 2,
        "fdp": 3,
        "grüne": 4,
        "gruene": 4,
        "bündnis 90/die grünen": 4,
        "linke": 5,
        "die linke": 5,
        "afd": 7,
        "bsw": 23,
        "fw": 8,
        "freie wähler": 8,
        "freie waehler": 8,
        "sonstige": 0,
        "andere": 0,
        "übrige": 0,
        "uebrige": 0,
        "pds": 5,
    }

    if name_lower in variations:
        return variations[name_lower]

    # Try partial match
    for key, id_val in lookup.items():
        if key in name_lower or name_lower in key:
            return id_val

    return None


def get_party_short_name(party_id: int) -> str | None:
    """Get party short name (Shortcut) by ID."""
    data = _load_json_cached("parties.json")
    party_data = data.get(str(party_id))
    if party_data:
        return party_data.get("Shortcut")
    return None


def get_party_name(party_id: int, fallback: str | None = None) -> str:
    """Return canonical party display name for an ID."""
    data = _load_json_cached("parties.json")
    item = data.get(str(party_id))
    if item:
        return item.get("Name") or item.get("Shortcut") or fallback or "Unknown"
    return fallback or "Unknown"


def get_party_shortcut(party_id: int) -> str | None:
    """Return canonical party shortcut for an ID."""
    return get_party_short_name(party_id)


# ============================================================================
# Method Mappings
# ============================================================================


@lru_cache(maxsize=1)
def _build_method_lookup() -> dict[str, int]:
    """Build lookup: normalized method name -> method ID."""
    data = _load_json("methods.json")
    lookup = {}

    for method_id, info in data.items():
        id_int = int(method_id)
        name = info.get("Name", "")

        if name:
            lookup[name.lower().strip()] = id_int

    return lookup


def map_method(name: str) -> int | None:
    """Map method name to ID.

    Args:
        name: Method name from scraper (e.g., "Telefonisch", "Online", "Telefon & Online")

    Returns:
        Method ID from JSON file, or None if not found
    """
    if not name:
        return None

    lookup = _build_method_lookup()

    name_lower = name.lower().strip()

    if name_lower in {"0", "99", "unbekannt", "unknown"}:
        return 0

    # Direct match
    if name_lower in lookup:
        return lookup[name_lower]

    # Try partial matches
    for key, id_val in lookup.items():
        if key in name_lower or name_lower in key:
            return id_val

    # Common patterns / variations
    if "telefon" in name_lower and "online" in name_lower:
        return 4  # Telefon & Online (TOM/TO)
    if "tom" in name_lower or "t-o-m" in name_lower:
        return 4  # Telefon & Online
    if "telefon" in name_lower:
        return 1  # Telefonisch
    if "online" in name_lower:
        return 3  # Online
    if "persönlich" in name_lower or "persoenlich" in name_lower:
        return 2  # Persönlich

    return None  # Unknown


def get_method_name(method_id: int, fallback: str | None = None) -> str:
    """Return canonical method name for an ID."""
    data = _load_json_cached("methods.json")
    item = data.get(str(method_id))
    if item and item.get("Name"):
        return item["Name"]
    return fallback or "Unknown"


# ============================================================================
# Tasker Mappings (for reference)
# ============================================================================


@lru_cache(maxsize=1)
def _build_tasker_lookup() -> dict[str, int]:
    """Build lookup: normalized tasker name -> tasker ID."""
    data = _load_json("taskers.json")
    lookup = {}

    for tasker_id, info in data.items():
        id_int = int(tasker_id)
        name = info.get("Name", "")

        if name:
            lookup[name.lower().strip()] = id_int

    return lookup


def map_tasker(name: str) -> int | None:
    """Map tasker name to ID.

    Args:
        name: Tasker name from scraper (e.g., "BILD", "RTL / n-tv")

    Returns:
        Tasker ID from JSON file, or None if not found
    """
    if not name:
        return None

    lookup = _build_tasker_lookup()

    name_lower = name.lower().strip()

    if name_lower in lookup:
        return lookup[name_lower]

    # Try partial matches
    for key, id_val in lookup.items():
        if key in name_lower or name_lower in key:
            return id_val

    return None


# ============================================================================
# Parliament/Election Mappings
# ============================================================================


@lru_cache(maxsize=1)
def _build_parliament_lookup() -> dict[str, int]:
    """Build lookup: parliament shortcut/scope -> parliament ID."""
    data = _load_json("parliaments.json")
    lookup = {}

    for parliament_id, info in data.items():
        id_int = int(parliament_id)

        # Map by Shortcut
        shortcut = info.get("Shortcut", "")
        if shortcut:
            lookup[shortcut.lower().strip()] = id_int

        # Map by Name
        name = info.get("Name", "")
        if name:
            lookup[name.lower().strip()] = id_int

        # Map by Election type
        election = info.get("Election", "")
        if election:
            lookup[election.lower().strip()] = id_int

        # Map by Aliases
        aliases = info.get("Aliases", [])
        for alias in aliases:
            if alias:
                lookup[alias.lower().strip()] = id_int

    return lookup


def map_parliament(scope: str) -> int:
    """Map scope/parliament to ID.

    Args:
        scope: Scope from scraper (e.g., "bayern", "berlin", "federal")

    Returns:
        Parliament ID from JSON file, or 0 (Bundestag) if not found
    """
    if not scope:
        return 0  # Bundestag

    lookup = _build_parliament_lookup()

    scope_lower = scope.lower().strip()

    variations = {
        "bund": 0,
        "ost": 0,
        "west": 0,
        "bw": 1,
        "by": 2,
        "be": 3,
        "bb": 4,
        "hb": 5,
        "hh": 6,
        "he": 7,
        "mv": 8,
        "ni": 9,
        "nw": 10,
        "nrw": 10,
        "rp": 11,
        "sl": 12,
        "sn": 13,
        "st": 14,
        "sh": 15,
        "th": 16,
    }
    if scope_lower in variations:
        return variations[scope_lower]

    # Direct match against all entries in JSON (Shortcut, Name, Election, Aliases)
    if scope_lower in lookup:
        return lookup[scope_lower]

    return 0  # Default to Bundestag


PARLIAMENT_SCOPE_BY_ID = {
    0: "federal",
    1: "bw",
    2: "by",
    3: "be",
    4: "bb",
    5: "hb",
    6: "hh",
    7: "he",
    8: "mv",
    9: "ni",
    10: "nrw",
    11: "rp",
    12: "sl",
    13: "sn",
    14: "st",
    15: "sh",
    16: "th",
    17: "eu",
}


def normalize_scope(scope: str | None) -> str:
    """Normalize raw scraper scope to the API-facing canonical scope code."""
    return PARLIAMENT_SCOPE_BY_ID.get(map_parliament(scope or ""), "federal")
