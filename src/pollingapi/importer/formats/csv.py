"""CSV loading helpers for imports."""

import csv
from pathlib import Path


def read_csv_rows(
    path: Path, delimiter: str = ",", encoding: str = "utf-8-sig"
) -> list[dict[str, str]]:
    """Read a CSV file into stripped dictionaries."""
    with path.open("r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        return [
            {
                (key or "").strip(): (value or "").strip()
                for key, value in row.items()
                if key and key.strip()
            }
            for row in reader
        ]
