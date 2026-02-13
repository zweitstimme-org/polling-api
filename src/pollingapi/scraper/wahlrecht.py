"""Wahlrecht.de scraper implementations."""

import re
from io import StringIO
from typing import Any, Dict, List

import pandas as pd

from pollingapi.scraper.base import BaseScraper
from pollingapi.scraper.config import ScraperRegistry
from pollingapi.scraper.schemas import filter_poll_payloads
from pollingapi.scraper.snapshots import save_table_snapshot


@ScraperRegistry.register("wahlrecht_bund")
class WahlrechtBundScraper(BaseScraper):
    """Scraper for federal Wahlrecht.de polling data."""

    def parse_url(self, url: str, url_config: Dict[str, Any]) -> pd.DataFrame:
        """Parse poll data from Wahlrecht.de URL."""
        html = self._fetch_html(url)
        tables = pd.read_html(StringIO(html), encoding="utf-8")

        if len(tables) < 2:
            self.logger.error(
                f"[{self.config.worker_name}] Could not find table at index 1 for {url} (found {len(tables)} tables)"
            )
            return pd.DataFrame()

        raw_df = tables[1].copy()

        # Save raw table snapshot for debugging
        safe_label = "".join(
            c for c in url.split("/")[-1] if c.isalnum() or c in ("-", "_")
        ).strip()[:40]
        save_table_snapshot(
            self.config.worker_name, raw_df, f"raw_{safe_label}", self.context.today_str
        )

        if raw_df.empty:
            self.logger.warning(f"[{self.config.worker_name}] Table at index 1 is empty for {url}")
            return pd.DataFrame()

        # Process the dataframe
        processed = self._normalize(raw_df, url_config)
        if processed is None or processed.empty:
            self.logger.warning(
                f"[{self.config.worker_name}] Normalization produced no rows for {url}"
            )
            return pd.DataFrame()

        # Apply drop footer if specified
        drop_footer = int(url_config.get("drop_footer", 0) or 0)
        if drop_footer > 0 and len(processed) > drop_footer:
            processed = processed.iloc[:-drop_footer]
        elif drop_footer > 0:
            self.logger.warning(
                f"[{self.config.worker_name}] Only {len(processed)} rows found for {url}; cannot drop {drop_footer} footer rows"
            )

        return processed

    def _normalize(self, df: pd.DataFrame, url_config: Dict[str, Any]) -> pd.DataFrame | None:
        """Normalize the raw dataframe."""
        cols = list(df.columns.astype(str))
        if not cols:
            return None

        # First column is always publish_date
        cols[0] = "publish_date"
        df = df.rename(columns=dict(zip(df.columns, cols, strict=False)))

        # Resolve party columns
        party_cols = self._resolve_party_columns(cols, url_config)
        if not party_cols:
            self.logger.error(
                f"[{self.config.worker_name}] Could not identify party columns using config: {url_config}"
            )
            return None

        valid_party_cols = [col for col in party_cols if col in df.columns]
        if not valid_party_cols:
            self.logger.error(
                f"[{self.config.worker_name}] Identified party columns not found: {party_cols}"
            )
            return None

        # Rename Befragte to respondents
        if "Befragte" in df.columns:
            df = df.rename(columns={"Befragte": "respondents"})

        # Create parties dict column
        df["parties"] = df.apply(lambda row: self._create_party_dict(row, valid_party_cols), axis=1)

        # Keep only relevant columns
        keep_cols = ["publish_date", "respondents", "Zeitraum", "parties"]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = None

        return df[keep_cols].copy()

    def _resolve_party_columns(self, cols: List[str], url_config: Dict[str, Any]) -> List[str]:
        """Resolve which columns contain party data."""
        # Strategy 1: Explicit party columns list
        if url_config.get("party_columns"):
            return [str(c) for c in url_config["party_columns"]]

        # Strategy 2: Boundary columns
        if url_config.get("party_start_after") or url_config.get("party_end_before"):
            start_after = url_config.get("party_start_after")
            end_before = url_config.get("party_end_before")
            try:
                start = cols.index(start_after) + 1 if start_after else 0
                end = cols.index(end_before) if end_before else len(cols)
                return cols[start:end]
            except ValueError:
                return []

        # Strategy 3: Numeric indices
        if (
            url_config.get("party_start_index") is not None
            or url_config.get("party_end_index") is not None
        ):
            start = int(url_config.get("party_start_index") or 0)
            end_index = url_config.get("party_end_index")
            end = int(end_index) + 1 if end_index is not None else len(cols)
            if start < 0 or end > len(cols) or start >= end:
                return []
            return cols[start:end]

        # Strategy 4: Auto-detect using unnamed/empty columns as boundaries
        boundary = [
            i
            for i, col in enumerate(cols)
            if not str(col).strip() or str(col).startswith("Unnamed")
        ]
        if len(boundary) >= 2:
            left, right = boundary[:2]
            return cols[left + 1 : right]

        return []

    def _create_party_dict(self, row: pd.Series, party_cols: List[str]) -> Dict[str, Any]:
        """Create dictionary of party results from row data."""
        party_dict: Dict[str, Any] = {}
        for col in party_cols:
            val = row.get(col)
            if pd.notna(val):
                parsed = self._parse_percentage(val)
                if parsed is not None:
                    party_dict[str(col)] = parsed
        return party_dict

    def _parse_percentage(self, value: Any) -> float | None:
        """Parse percentage value."""
        if pd.isna(value):
            return None
        try:
            val_str = str(value).replace("%", "").replace(",", ".").strip()
            return float(val_str)
        except (ValueError, TypeError):
            return None


@ScraperRegistry.register("wahlrecht_land")
class WahlrechtLandScraper(BaseScraper):
    """Scraper for state-level Wahlrecht.de polling data."""

    def __init__(self, *args, **kwargs):
        """Initialize with HTML cache."""
        super().__init__(*args, **kwargs)
        self._html_cache: Dict[str, str] = {}

    def select_urls(self) -> List[Dict[str, Any]]:
        """Always process all URLs for state scrapers (they use table_index to get different data)."""
        return self.config.urls

    def parse_url(self, url: str, url_config: Dict[str, Any]) -> pd.DataFrame:
        """Parse poll data from state Wahlrecht.de URL."""
        table_index = url_config.get("table_index", 0)

        # Use cached HTML or fetch new
        if url not in self._html_cache:
            self._html_cache[url] = self._fetch_html(url)

        html = self._html_cache[url]
        tables = pd.read_html(StringIO(html), encoding="utf-8")

        # Filter for tables with enough columns (metadata + at least one party)
        valid_tables = [t for t in tables if len(t.columns) >= 4]

        if table_index >= len(valid_tables):
            self.logger.warning(
                f"[{self.config.worker_name}] Table index {table_index} out of range (found {len(valid_tables)} valid tables)"
            )
            return pd.DataFrame()

        df = valid_tables[table_index].copy()

        # Save raw snapshot
        safe_label = f"raw_table_{table_index}"
        save_table_snapshot(self.config.worker_name, df, safe_label, self.context.today_str)

        # Drop header and footer rows
        drop_header = int(url_config.get("drop_header", 1) or 1)
        drop_footer = int(url_config.get("drop_footer", 3) or 3)

        if drop_header > 0:
            df = df.iloc[drop_header:]
        if drop_footer > 0 and len(df) > drop_footer:
            df = df.iloc[:-drop_footer]

        # Process the dataframe
        return self._process_state_df(df)

    def _process_state_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process state polling dataframe."""
        if len(df.columns) < 4:
            return pd.DataFrame()

        # Log column structure for debugging
        self.logger.debug(f"Table columns: {df.columns.tolist()}")

        # Split into metadata and party columns
        # Wahlrecht state format: Institut | Auftraggeber | Befragte | Datum | (optional unnamed) | [Parties...]
        # Find the first party column by looking for known party names or non-unnamed columns after metadata
        meta_cols = list(df.columns[:4])

        # Find where party columns start (after metadata and any unnamed columns)
        party_start_idx = 4
        for i in range(4, len(df.columns)):
            col_name = str(df.columns[i])
            # Skip empty or unnamed columns
            if not col_name.strip() or col_name.startswith("Unnamed"):
                party_start_idx = i + 1
            else:
                break

        party_cols = list(df.columns[party_start_idx:])

        # Rename metadata columns to standard names
        df = df.rename(
            columns={
                meta_cols[0]: "institute",
                meta_cols[1]: "tasker",
                meta_cols[2]: "respondents_raw",
                meta_cols[3]: "publish_date",
            }
        )

        # Parse respondents field (contains count, date range, method)
        df["respondents_parsed"] = df["respondents_raw"].apply(self._parse_respondents_field)

        # Extract parsed values
        # Convert respondents to string to match schema
        df["respondents"] = df["respondents_parsed"].apply(
            lambda x: str(x[0]) if x[0] is not None else None
        )
        df["Zeitraum"] = df["respondents_parsed"].apply(lambda x: x[1])

        # Create parties dict
        df["parties"] = df.apply(
            lambda row: {
                col: self._parse_percentage(row[col])
                for col in party_cols
                if pd.notna(row[col]) and self._parse_percentage(row[col]) is not None
            },
            axis=1,
        )

        # Keep only relevant columns
        keep_cols = ["publish_date", "respondents", "Zeitraum", "parties", "tasker"]
        df = df[[col for col in keep_cols if col in df.columns]]

        return df

    def _parse_respondents_field(self, value: Any) -> tuple[int | None, str | None]:
        """Parse respondents field to extract count and timeframe."""
        if pd.isna(value):
            return None, None

        val_str = str(value)

        # Extract count (e.g., "1.503" -> 1503)
        count_match = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)", val_str)
        count = int(count_match.group(1).replace(".", "")) if count_match else None

        # Extract timeframe (e.g., "01.–05.03.2024")
        # Pattern: DD.–DD.MM.YYYY or DD.MM.–DD.MM.YYYY
        timeframe_match = re.search(r"(\d{1,2}\.\s*[–-]\s*\d{1,2}\.\d{2}\.\d{4})", val_str)
        if not timeframe_match:
            # Try alternative pattern
            timeframe_match = re.search(
                r"(\d{1,2}\.\d{2}\.\s*[–-]\s*\d{1,2}\.\d{2}\.\d{4})", val_str
            )

        timeframe = timeframe_match.group(1) if timeframe_match else None

        return count, timeframe

    def _parse_percentage(self, value: Any) -> float | None:
        """Parse percentage value."""
        if pd.isna(value):
            return None
        try:
            val_str = str(value).replace("%", "").replace(",", ".").strip()
            return float(val_str)
        except (ValueError, TypeError):
            return None

    def run(self) -> int:
        """Run the scraper with HTML caching."""
        urls = self.select_urls()
        if not urls:
            self.logger.info(f"No URLs to process for {self.config.worker_name}")
            return 0

        total_inserted = 0
        self.logger.info(f"Processing {len(urls)} URLs for {self.config.worker_name}")

        for url_config in urls:
            url = url_config.get("url") if isinstance(url_config, dict) else url_config
            if not url:
                continue

            try:
                self.logger.info(f"Processing: {url}")

                # Parse data (HTML is cached internally)
                df = self.parse_url(url, url_config if isinstance(url_config, dict) else {})
                if df.empty:
                    self.logger.warning(f"No data found at {url}")
                    continue

                # Apply metadata
                df = self._apply_metadata(df)

                # Filter and validate
                records = df.to_dict("records")
                payloads = filter_poll_payloads(records)

                # Insert into database
                inserted = self.post_polls(payloads)
                total_inserted += inserted
                self.logger.info(f"Inserted {inserted} polls from {url}")

            except Exception as e:
                self.logger.error(f"Error processing {url}: {e}")
                if self.context.debug:
                    raise
                continue

        # Mark initial run complete
        self._mark_initial_run_complete()

        self.logger.info(f"Total inserted: {total_inserted}")
        return total_inserted
