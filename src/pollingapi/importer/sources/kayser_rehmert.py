"""Importer for Kayser/Rehmert coalition inclusion probability polling data."""

import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pollingapi.importer.schemas import RawPollImport
from pollingapi.importer.sources.base import ImportSource

COUNTRY_ISO3C = "DEU"
PROVIDER = "Kayser/Rehmert"
WORKER = "import:kayser_rehmert"
SOURCE = "xlsx_import:kayser_rehmert"

GROUP_COLUMNS = ("survey_date", "institute")

PARTY_NAME_MAP = {
    "AfD": "AfD",
    "BSW": "BSW",
    "CDU/CSU": "CDU/CSU",
    "FDP": "FDP",
    "FW": "FW",
    "Greens": "Grüne",
    "Other": "Sonstige",
    "PDS/Linke": "Linke",
    "SPD": "SPD",
}

INSTITUTE_NAME_MAP = {
    "Emnid": "Verian (Emnid)",
    "Infratest dimap": "Infratest Dimap",
    "Pollytix": "pollytix",
    "Wahlkreisprognose": "Institut Wahlkreisprognose",
}


class KayserRehmertImportSource(ImportSource):
    """Load Germany-only poll rows from the Kayser/Rehmert XLSX file."""

    name = "kayser_rehmert"

    def load(self, path: Path) -> list[RawPollImport]:
        frame = pd.read_excel(path, sheet_name="Table1", dtype=object)
        frame = _normalize_frame(frame)
        frame = frame[
            frame["country_iso3c"].eq(COUNTRY_ISO3C) & frame["original_date"].eq("1")
        ].copy()

        imports: list[RawPollImport] = []
        for _, group in frame.groupby(list(GROUP_COLUMNS), dropna=False, sort=False):
            parties = _party_results(group.to_dict(orient="records"))
            if parties is None:
                continue

            first = group.iloc[0].to_dict()
            publish_date = _format_date(first["survey_date"])
            if publish_date is None:
                continue

            imports.append(
                RawPollImport(
                    publish_date=publish_date,
                    parties=parties,
                    institute_id=_map_institute(first["institute"]),
                    provider=PROVIDER,
                    source=SOURCE,
                    scope="Bund",
                    election_id="Bundestagswahl",
                    method_id="99",
                    worker=WORKER,
                )
            )

        return imports


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in (
        "country_iso3c",
        "institute",
        "original_date",
        "party_name_short",
        "poll",
        "source",
    ):
        normalized[column] = normalized[column].fillna("").astype(str).str.strip()
    return normalized


def _party_results(rows: Iterable[dict[str, Any]]) -> dict[str, str] | None:
    values_by_party: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        party = PARTY_NAME_MAP.get(str(row["party_name_short"]).strip())
        value = _format_number(row["poll"])
        if party is None or value is None:
            continue
        values_by_party[party].append(value)

    parties: dict[str, str] = {}
    for party, values in values_by_party.items():
        unique_values = sorted(set(values))
        if len(unique_values) > 1:
            return None
        parties[party] = unique_values[0]

    return parties or None


def _format_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:\s+00:00:00)?", text):
        return text[:10]

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _format_number(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    number = float(text)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _map_institute(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        return "Unknown"

    if " Archived " in name:
        name = name.split(" Archived ", 1)[0].strip()
    if name.endswith("(intermediate result)"):
        name = name.removesuffix("(intermediate result)").strip()
    if name.endswith("(MRP)"):
        name = name.removesuffix("(MRP)").strip()

    return INSTITUTE_NAME_MAP.get(name, name)
