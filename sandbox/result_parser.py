# %% Imports
import json
import re
from dataclasses import dataclass, field

from pollingapi.scraper.datamodel import Party, PartyResult  # your new models

# %% Raw name → Party mapping
# Maps scraped abbreviations / alternate spellings to canonical Party enum members
PARTY_NAME_MAP: dict[str, Party] = {
    "cdu": Party.CDU,
    "csu": Party.CSU,
    "cdu/csu": Party.CDU_CSU,
    "union": Party.CDU_CSU,
    "spd": Party.SPD,
    "grüne": Party.GRUENE,
    "gruene": Party.GRUENE,
    "die grünen": Party.GRUENE,
    "b90/grüne": Party.GRUENE,
    "bündnis 90/die grünen": Party.GRUENE,
    "fdp": Party.FDP,
    "afd": Party.AFD,
    "alternative für deutschland": Party.AFD,
    "linke": Party.LINKE,
    "die linke": Party.LINKE,
    "bsw": Party.BSW,
    "bündnis sahra wagenknecht": Party.BSW,
    "fw": Party.FREIE_WAEHLER,
    "freie wähler": Party.FREIE_WAEHLER,
    "volt": Party.VOLT,
    "ssw": Party.SSW,
    "sonstige": Party.SONSTIGE,
    "andere": Party.SONSTIGE,
    "and.": Party.SONSTIGE,
}


# %% Non-result column names to filter out
NON_RESULT_NAMES: frozenset[str] = frozenset(
    {
        "nichtwähler",
        "nicht-wähler",
        "nichtwähler/unentschl.",
        "nichtwähler/unentschlos.",
        "unentschlossene",
        "unent-schlossene",
        "summe",
        "quelle",
    }
)


# %% Helpers
def _normalise_name(raw: str) -> str:
    """Lowercase and strip a party name for lookup."""
    return re.sub(r"\s+", " ", raw.lower().strip())


def _resolve_party(raw_name: str) -> Party | None:
    """Resolve a raw scraped party name to a canonical Party enum member."""
    key = _normalise_name(raw_name)
    return PARTY_NAME_MAP.get(key)


def _is_non_result_name(raw_name: str) -> bool:
    return _normalise_name(raw_name) in NON_RESULT_NAMES


def _parse_percentage(raw: object) -> float | None:
    """Normalise a raw percentage value to a float.

    Handles German decimal comma, trailing %, dash placeholders, and ranges.
    """
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return float(raw)

    text = str(raw).strip().replace("\xa0", " ").replace("%", "").strip()

    if not text or text in {"-", "–", "—", "−"}:
        return None

    text = text.replace(",", ".")

    range_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        return (float(range_match.group(1)) + float(range_match.group(2))) / 2

    try:
        return float(text)
    except ValueError:
        return None


# %% Parse result container
@dataclass
class PartyResultEntry:
    """Intermediate parse result before promotion to PartyResult."""

    raw_name: str
    party: Party | None
    value: float | None
    parse_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.party is not None and self.value is not None

    def to_party_result(self) -> PartyResult:
        """Promote to final PartyResult. Only call when is_valid is True."""
        assert self.party is not None and self.value is not None
        return PartyResult(party=self.party, value=self.value)


@dataclass
class PollResultParseResult:
    """Structured outcome of parsing a full parties payload."""

    entries: list[PartyResultEntry] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def valid_entries(self) -> list[PartyResultEntry]:
        return [e for e in self.entries if e.is_valid]

    @property
    def party_results(self) -> list[PartyResult]:
        """Final PartyResult objects — ready to persist."""
        return [e.to_party_result() for e in self.valid_entries]

    @property
    def failed_entries(self) -> list[PartyResultEntry]:
        return [e for e in self.entries if not e.is_valid]

    @property
    def is_complete(self) -> bool:
        return bool(self.party_results) and self.parse_error is None


# %% Core parser
def parse_party_results(parties_json: str | None) -> PollResultParseResult:
    """Parse a raw parties JSON payload into structured PartyResult objects.

    Args:
        parties_json: Raw JSON string from the parties column, e.g.
                      '{"CDU/CSU": "32,1", "SPD": "16,5", "Summe": "100"}'
    Returns:
        PollResultParseResult — use .party_results to get the final
        List[PartyResult] for persistence, .failed_entries for diagnostics.
    """
    if not parties_json or not parties_json.strip():
        return PollResultParseResult(parse_error="Empty or missing parties payload")

    try:
        raw: dict[str, object] = json.loads(parties_json)
    except json.JSONDecodeError as exc:
        return PollResultParseResult(parse_error=f"JSON decode failed: {exc}")

    if not isinstance(raw, dict):
        return PollResultParseResult(parse_error=f"Expected JSON object, got {type(raw).__name__}")

    entries: list[PartyResultEntry] = []
    skipped: list[str] = []

    for raw_name, raw_value in raw.items():
        if _is_non_result_name(raw_name):
            skipped.append(raw_name)
            continue

        party = _resolve_party(raw_name)
        value = _parse_percentage(raw_value)

        error: str | None = None
        if party is None:
            error = f"Unknown party name: '{raw_name}'"
        elif value is None:
            error = f"Could not parse percentage: '{raw_value}'"

        entries.append(
            PartyResultEntry(
                raw_name=raw_name,
                party=party,
                value=value,
                parse_error=error,
            )
        )

    return PollResultParseResult(entries=entries, skipped=skipped)


# %% Smoke test payload
_EXAMPLE = json.dumps(
    {
        "CDU/CSU": "32,1",
        "SPD": "16,5 %",
        "Grüne": "13,0",
        "FDP": "5–7",
        "AfD": "18,2",
        "BSW": "–",  # placeholder → value=None → failed
        "Linke": "3,1",
        "Summe": "100",  # skipped
        "Quelle": "Forsa",  # skipped
        "Unbekannt XYZ": "2",  # unknown party → failed
    }
)

result = parse_party_results(_EXAMPLE)

# %% Top-level summary
print(f"complete:  {result.is_complete}")
print(f"skipped:   {result.skipped}")
print(f"error:     {result.parse_error}")

# %% All entries with status
for e in result.entries:
    status = "✓" if e.is_valid else "✗"
    print(f"  {status}  {e.raw_name:<25} party={e.party}  value={e.value}  err={e.parse_error}")

# %% Final PartyResult objects — what goes into the DB
for pr in result.party_results:
    print(f"  → {pr.party.name:<15}  {pr.value}%")
