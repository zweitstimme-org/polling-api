"""XLSX loading helpers for imports."""

from pathlib import Path
from typing import Any

import pandas as pd


def read_xlsx_rows(
    path: Path,
    sheet_name: str | int = 0,
    header: int = 0,
) -> list[dict[str, str]]:
    """Read an XLSX worksheet into stripped dictionaries."""
    frame = pd.read_excel(path, sheet_name=sheet_name, header=header, dtype=object)
    frame = frame.where(pd.notna(frame), "")

    rows: list[dict[str, str]] = []
    for row in frame.to_dict(orient="records"):
        rows.append(
            {
                _stringify(key).strip(): _stringify(value).strip()
                for key, value in row.items()
                if _stringify(key).strip()
            }
        )
    return rows


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
