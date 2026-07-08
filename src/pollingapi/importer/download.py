"""Download helpers for importer input files."""

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from pollingapi.core import PROJECT_ROOT
from pollingapi.importer.runner import IMPORTS_DIR

DEFAULT_MANIFEST = PROJECT_ROOT / "import_urls.txt"


@dataclass(frozen=True)
class DownloadSpec:
    """One file download declared in the import URL manifest."""

    destination: Path
    url: str


@dataclass(frozen=True)
class DownloadResult:
    """Result for one attempted download."""

    destination: Path
    url: str
    downloaded: bool
    bytes_written: int


Downloader = Callable[[str, Path, float], int]


def read_download_manifest(path: Path = DEFAULT_MANIFEST) -> list[DownloadSpec]:
    """Read import download specs from a text manifest.

    Supported line formats:
        filename.xlsx https://example.com/file.xlsx
        https://example.com/file.xlsx

    Blank lines and lines starting with ``#`` are ignored.
    """
    specs: list[DownloadSpec] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        specs.append(_parse_manifest_line(line, line_number))
    return specs


def download_from_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    imports_dir: Path = IMPORTS_DIR,
    force: bool = False,
    timeout: float = 60.0,
    downloader: Downloader | None = None,
) -> list[DownloadResult]:
    """Download all files declared in the manifest into the imports directory."""
    imports_dir.mkdir(parents=True, exist_ok=True)
    download = downloader or download_url
    results: list[DownloadResult] = []

    for spec in read_download_manifest(manifest_path):
        destination = _resolve_destination(imports_dir, spec.destination)
        if destination.exists() and not force:
            results.append(
                DownloadResult(
                    destination=destination,
                    url=spec.url,
                    downloaded=False,
                    bytes_written=destination.stat().st_size,
                )
            )
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = download(spec.url, destination, timeout)
        results.append(
            DownloadResult(
                destination=destination,
                url=spec.url,
                downloaded=True,
                bytes_written=bytes_written,
            )
        )

    return results


def download_url(url: str, destination: Path, timeout: float = 60.0) -> int:
    """Download a URL to a local file and return the written byte count."""
    bytes_written = 0
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        with destination.open("wb") as file:
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                file.write(chunk)
                bytes_written += len(chunk)
    return bytes_written


def _parse_manifest_line(line: str, line_number: int) -> DownloadSpec:
    parts = shlex.split(line)
    if len(parts) == 1:
        url = parts[0]
        destination = Path(_filename_from_url(url))
    elif len(parts) == 2:
        destination = Path(parts[0])
        url = parts[1]
    else:
        raise ValueError(
            f"Invalid import URL manifest line {line_number}: expected URL or 'filename URL'"
        )

    if destination.is_absolute() or ".." in destination.parts:
        raise ValueError(f"Invalid destination on manifest line {line_number}: {destination}")

    return DownloadSpec(destination=destination, url=url)


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    if not filename:
        raise ValueError(f"Cannot infer filename from URL: {url}")
    return filename


def _resolve_destination(imports_dir: Path, destination: Path) -> Path:
    resolved = imports_dir / destination
    if not resolved.resolve().is_relative_to(imports_dir.resolve()):
        raise ValueError(f"Download destination escapes imports directory: {destination}")
    return resolved
