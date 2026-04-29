"""Snapshot utilities for saving scraper outputs."""

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from pollingapi.core import DATA_DIR


def _sanitize_filename(name: str) -> str:
    """Sanitize string for use in filename."""
    return re.sub(r"[^\w\-_.]", "_", name)


def save_html_snapshot(worker_name: str, url: str, html: str, date_str: str) -> Path:
    """Save HTML snapshot to disk."""
    html_dir = DATA_DIR / worker_name / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{date_str}_{_sanitize_filename(url.split('/')[-1])}.html"
    filepath = html_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath


def save_table_snapshot(worker_name: str, df: pd.DataFrame, label: str, date_str: str) -> Path:
    """Save DataFrame as table snapshot."""
    tables_dir = DATA_DIR / worker_name / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{date_str}_{_sanitize_filename(label)}.csv"
    filepath = tables_dir / filename

    df.to_csv(filepath, index=False, encoding="utf-8")
    return filepath


# Old function name: save_normalized_snapshot(worker_name: str, df: pd.DataFrame, label: str, date_str: str) -> Path:
def save_csv_snapshot(worker_name: str, df: pd.DataFrame, label: str, date_str: str) -> Path:
    """Save normalized DataFrame snapshot."""
    csvs_dir = DATA_DIR / worker_name / "csvs"
    csvs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{date_str}_{worker_name}_{_sanitize_filename(label)}.csv"
    filepath = csvs_dir / filename

    df.to_csv(filepath, index=False, encoding="utf-8")
    return filepath


def save_json_snapshot(worker: str, data: Any, label: str, date_str: str) -> Path:
    """Save JSON data snapshot (for API dumps).
    Args:
        worker: Worker name (e.g., "dawum")
        data: Data to serialize (dict, list, or object)
        label: Label for the snapshot (e.g., "api_dump", "wrangled")
        date_str: Date string (e.g., "2026-04-27")
    Returns:
        Path to saved JSON file.
    """
    json_dir = DATA_DIR / worker / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date_str}_{_sanitize_filename(label)}.json"
    filepath = json_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return filepath


def save_debug_snapshot(worker_name: str, data: dict[str, Any], timestamp: str) -> Path:
    """Save debug snapshot with aggregated data."""
    debug_dir = DATA_DIR / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{worker_name}_debug_output_{timestamp}.csv"
    filepath = debug_dir / filename

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Handle parties column - convert dict to JSON string
    if "parties" in df.columns:
        df["parties"] = df["parties"].apply(
            lambda x: json.dumps(x, sort_keys=True) if isinstance(x, dict) else x
        )

    df.to_csv(filepath, index=False, encoding="utf-8")
    return filepath
