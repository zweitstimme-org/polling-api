"""EU federal (Europawahl) scraper worker."""

import re
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.snapshots import save_table_snapshot
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class EuFedScraper(WahlrechtBundScraper):
    """Scraper for Wahlrecht.de Europawahl polling data."""

    def parse_url(self, url: str, url_config: dict[str, Any]) -> pd.DataFrame:
        """Parse poll data from configured EU table index."""
        html = self._fetch_html(url)
        tables = pd.read_html(StringIO(html), encoding="utf-8")

        table_index = int(url_config.get("table_index", 1) or 1)
        if table_index >= len(tables):
            self.logger.warning(
                f"[{self.config.worker_name}] Table index {table_index} out of range for {url} (found {len(tables)} tables)"
            )
            return pd.DataFrame()

        raw_df = tables[table_index].copy()
        save_table_snapshot(
            self.config.worker_name,
            raw_df,
            f"raw_table_{table_index}",
            self.context.today_str,
        )

        if raw_df.empty:
            return pd.DataFrame()

        processed = self._normalize(raw_df, url_config)
        if processed is None or processed.empty:
            return pd.DataFrame()

        return processed

    def _apply_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply metadata while preserving row-level institute values."""
        df = df.copy()
        df["scope"] = self.config.scope
        df["election_id"] = self.config.election_id
        df["method_id"] = self.config.method_id
        df["provider"] = self.config.provider
        df["source"] = self.config.source

        if "institute_id" not in df.columns:
            df["institute_id"] = self.config.institute_id
        else:
            df["institute_id"] = df["institute_id"].where(df["institute_id"].notna(), None)
            df.loc[df["institute_id"].isna(), "institute_id"] = self.config.institute_id

        df["date_downloaded"] = datetime.now().isoformat()
        return df

    def _normalize(self, df: pd.DataFrame, url_config: dict[str, Any]) -> pd.DataFrame | None:
        """Normalize EU table and map into the raw poll schema."""
        cols = list(df.columns.astype(str))
        if not cols:
            return None

        # First column is always the date column in Wahlrecht tables.
        cols[0] = "publish_date"
        df = df.rename(columns=dict(zip(df.columns, cols, strict=False)))

        # Column header variants on this page:
        # - "Institut"
        # - "Auftrag- geber"
        # - "Befragte Zeitraum"
        rename_map: dict[str, str] = {}
        for col in df.columns:
            c = str(col)
            c_norm = re.sub(r"\s+", " ", c).strip()
            c_flat = c_norm.replace(" ", "")
            if c_norm == "Institut":
                rename_map[c] = "institute_id"
            elif c_flat in {"Auftrag-geber", "Auftraggeber"}:
                rename_map[c] = "tasker"
            elif c_norm == "Befragte Zeitraum":
                rename_map[c] = "Befragte"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Keep only poll rows (table also contains election result rows).
        if "publish_date" in df.columns:
            date_mask = (
                df["publish_date"].astype(str).str.strip().str.match(r"^\d{2}\.\d{2}\.\d{4}$")
            )
            df = df.loc[date_mask].copy()
            if df.empty:
                return None

        # Preserve the unparsed combined field in both schema-compatible places.
        # This keeps maximum information without parsing respondents/timeframe.
        if "Befragte" in df.columns and "Zeitraum" not in df.columns:
            df["Zeitraum"] = df["Befragte"]

        party_cols = self._resolve_party_columns(list(df.columns.astype(str)), url_config)
        if not party_cols:
            return None

        valid_party_cols = [col for col in party_cols if col in df.columns]
        if not valid_party_cols:
            return None

        df["parties"] = df.apply(lambda row: self._create_party_dict(row, valid_party_cols), axis=1)

        keep_cols = ["publish_date", "institute_id", "tasker", "Befragte", "Zeitraum", "parties"]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = None

        return df.loc[:, keep_cols].copy()

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for EU federal scraper."""
        return ScraperConfig(
            worker_name="eu_fed",
            institute_id="various",
            provider="eu_fed",
            source="html_scraper",
            scope="eu",
            election_id="Europawahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/europawahl.htm",
                    "table_index": 1,
                    "party_columns": [
                        "CDU",
                        "CSU",
                        "SPD",
                        "GRÜNE",
                        "FDP",
                        "LINKE",
                        "AfD",
                        "PIR",
                        "FW",
                        "TSP",
                        "PARTEI",
                        "BSW",
                        "Volt",
                        "Sonstige",
                    ],
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/europawahl.htm",
                    "table_index": 2,
                    "party_columns": [
                        "CDU",
                        "CSU",
                        "SPD",
                        "GRÜNE",
                        "FDP",
                        "LINKE",
                        "Sonstige",
                    ],
                },
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return EuFedScraper.get_config()
