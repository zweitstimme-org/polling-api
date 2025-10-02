# app/main.py
from pathlib import Path
from typing import List

import httpx
import pandas as pd

# ---- Config ----
DATA_PATH = Path("./data")
DATA_PATH.mkdir(exist_ok=True)
RESULTS_FILE = DATA_PATH / "election_dates.json"


def rename_cols(df: pd.DataFrame) -> pd.DataFrame:
    new_names = {
        "Jahr": "year",
        "Datum": "date",
        "Land": "land",
        "Art": "level",
        "Turnus": "interval_years",
    }
    return df.rename(columns=new_names)


def combine_date_and_year(
    df: pd.DataFrame, date_col="date", year_col="year"
) -> pd.DataFrame:
    def parse_row(row):
        raw_date = str(row[date_col]).strip()
        year = str(row[year_col])

        if (
            pd.notna(raw_date)
            and len(raw_date.split(".")) >= 2
            and raw_date[0:2].isdigit()
        ):
            cleaned = raw_date.rstrip(".")
            try:
                parsed = pd.to_datetime(f"{cleaned}.{year}", format="%d.%m.%Y")
                return parsed.strftime("%Y-%m-%d")
            except Exception:
                return f"{year}-01-01"
        else:
            return f"{year}-01-01"

    df["date"] = df.apply(parse_row, axis=1)
    return df


def mark_estimates(df: pd.DataFrame, date_col="date") -> pd.DataFrame:
    df["estimate"] = df[date_col].astype(str).str.endswith("-01-01")
    return df


async def scrape_dates() -> List[dict]:
    url = "https://www.bundeswahlleiterin.de/service/wahltermine.html"

    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        r.raise_for_status()
        html = r.text

    df = pd.read_html(html)[0]
    df = rename_cols(df)
    df = combine_date_and_year(df)
    df = mark_estimates(df)

    df.to_json(RESULTS_FILE, orient="records", force_ascii=False, indent=2)
    return df.to_dict(orient="records")
