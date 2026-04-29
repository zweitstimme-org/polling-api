"""Parse raw party result payloads into canonical party results."""

import json
import re
from dataclasses import dataclass, field

from pollingapi.scraper.datamodel import Party, PartyResult

PARTY_NAME_MAP: dict[str, Party] = {
    "afd": Party.AFD,
    "alternative für deutschland": Party.AFD,
    "and.": Party.SONSTIGE,
    "andere": Party.SONSTIGE,
    "bd": Party.BD,
    "bayernpartei": Party.BAYERNPARTEI,
    "bp": Party.BAYERNPARTEI,
    "bsw": Party.BSW,
    "bündnis sahra wagenknecht": Party.BSW,
    "bvb/fw": Party.BVB_FW,
    "cdu": Party.CDU,
    "cdu/csu": Party.CDU_CSU,
    "csu": Party.CSU,
    "die grünen": Party.GRUENE,
    "die linke": Party.LINKE,
    "die partei": Party.DIE_PARTEI,
    "familie": Party.FAMILIE,
    "fdp": Party.FDP,
    "fw": Party.FREIE_WAEHLER,
    "freie wähler": Party.FREIE_WAEHLER,
    "freie waehler": Party.FREIE_WAEHLER,
    "grüne": Party.GRUENE,
    "gruene": Party.GRUENE,
    "b90/grüne": Party.GRUENE,
    "bündnis 90/die grünen": Party.GRUENE,
    "linke": Party.LINKE,
    "npd": Party.NPD,
    "ödp": Party.OEDP,
    "oedp": Party.OEDP,
    "piraten": Party.PIRATEN,
    "sonstige": Party.SONSTIGE,
    "spd": Party.SPD,
    "ssw": Party.SSW,
    "tierschutzpartei": Party.TIERSCHUTZPARTEI,
    "union": Party.CDU_CSU,
    "volt": Party.VOLT,
    "werteunion": Party.WERTEUNION,
}

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


def normalize_result_name(raw: str) -> str:
    """Normalize a scraped party/result column name for lookup."""
    return re.sub(r"\s+", " ", raw.lower().strip())


def resolve_party(raw_name: str) -> Party | None:
    """Resolve a scraped party label to a canonical party enum member."""
    key = normalize_result_name(raw_name)
    if key in PARTY_NAME_MAP:
        return PARTY_NAME_MAP[key]

    simplified = re.sub(r"[^\w\s/]", "", key)
    return PARTY_NAME_MAP.get(simplified)


def is_non_result_name(raw_name: str) -> bool:
    """Return True when a raw result column is metadata, not a party result."""
    return normalize_result_name(raw_name) in NON_RESULT_NAMES


def parse_percentage(raw: object) -> float | None:
    """Parse a scraped percentage value to a float."""
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
        start, end = range_match.groups()
        return (float(start) + float(end)) / 2

    matches = re.findall(r"\d+(?:\.\d+)?", text)
    if not matches:
        return None

    try:
        return sum(float(match) for match in matches)
    except ValueError:
        return None


@dataclass
class PartyResultEntry:
    """Intermediate party parse result with diagnostics."""

    raw_name: str
    party: Party | None
    value: float | None
    parse_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.party is not None and self.value is not None

    def to_party_result(self) -> PartyResult:
        """Promote a valid intermediate entry to the domain result model."""
        if self.party is None or self.value is None:
            raise ValueError("Cannot convert invalid party result entry")
        return PartyResult(party=self.party, value=self.value)


@dataclass
class PollResultParseResult:
    """Structured outcome of parsing a raw parties payload."""

    entries: list[PartyResultEntry] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def valid_entries(self) -> list[PartyResultEntry]:
        return [entry for entry in self.entries if entry.is_valid]

    @property
    def failed_entries(self) -> list[PartyResultEntry]:
        return [entry for entry in self.entries if not entry.is_valid]

    @property
    def party_results(self) -> list[PartyResult]:
        return [entry.to_party_result() for entry in self.valid_entries]

    @property
    def is_complete(self) -> bool:
        return bool(self.party_results) and self.parse_error is None and not self.failed_entries


def parse_party_results(parties_json: str | None) -> PollResultParseResult:
    """Parse raw parties JSON into canonical party result objects."""
    if not parties_json or not parties_json.strip():
        return PollResultParseResult(parse_error="Empty or missing parties payload")

    try:
        raw = json.loads(parties_json)
    except json.JSONDecodeError as exc:
        return PollResultParseResult(parse_error=f"JSON decode failed: {exc}")

    if not isinstance(raw, dict):
        return PollResultParseResult(parse_error=f"Expected JSON object, got {type(raw).__name__}")

    entries: list[PartyResultEntry] = []
    skipped: list[str] = []
    seen: set[Party] = set()

    for raw_name, raw_value in raw.items():
        if is_non_result_name(raw_name):
            skipped.append(raw_name)
            continue

        # TODO: Split compound result cells such as
        # "Sonstige": "BSW 2 %BP 1 %Sonst. 5 %" into individual party results.
        # Some state poll tables encode minor parties this way; storing the
        # summed value as SONSTIGE preserves totals but loses party detail.
        party = resolve_party(raw_name)
        value = parse_percentage(raw_value)
        error: str | None = None
        if party is None:
            error = f"Unknown party name: {raw_name!r}"
        elif value is None:
            error = f"Could not parse percentage: {raw_value!r}"
        elif party in seen:
            error = f"Duplicate party result: {party.name}"

        if party is not None and error is None:
            seen.add(party)

        entries.append(
            PartyResultEntry(
                raw_name=raw_name,
                party=party,
                value=value,
                parse_error=error,
            )
        )

    return PollResultParseResult(entries=entries, skipped=skipped)
