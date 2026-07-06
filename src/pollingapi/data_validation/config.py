"""Configuration for data validation checks."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pollingapi.core import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "validation.toml"


@dataclass(frozen=True)
class CorePartyConfig:
    """Year thresholds for expected core parties."""

    green_from_year: int = 1990
    afd_from_year: int = 2014
    fdp_until_year: int = 2021


@dataclass(frozen=True)
class ReportingConfig:
    """Thresholds for validation reporting and health status."""

    min_valid_share: float = 0.90
    max_warning_share: float = 0.10
    max_invalid_share: float = 0.05


@dataclass(frozen=True)
class PollMatchingConfig:
    """Thresholds for linking equivalent polls across providers."""

    date_window_days: int = 7
    primary_provider: str = "wahlrecht.de"
    secondary_provider: str = "DAWUM"
    result_parties: tuple[str, ...] = ("SPD", "AFD")
    max_party_delta: float = 1.0
    max_total_delta: float = 1.5
    survey_date_tolerance_days: int = 0
    respondent_tolerance: int = 0
    min_score_gap: float = 0.01


@dataclass(frozen=True)
class ValidationConfig:
    """Runtime configuration for data validation."""

    sum_tolerance: float
    jump_threshold: float
    respondent_limits: dict[str, tuple[int, int]]
    respondent_default: tuple[int, int]
    core_parties: CorePartyConfig
    reporting: ReportingConfig
    poll_matching: PollMatchingConfig


DEFAULT_RESPONDENT_LIMITS = {
    "TELEFONISCH": (700, 4000),
    "ONLINE": (500, 6000),
    "TELEFON_ONLINE": (700, 4000),
    "PERSOENLICH": (500, 3000),
    "UNBEKANNT": (500, 6000),
}


@lru_cache
def get_validation_config(config_path: Path = CONFIG_PATH) -> ValidationConfig:
    """Load validation config from TOML."""
    data = _load_toml(config_path)
    respondents = data.get("respondents", {})
    core_parties = data.get("core_parties", {})
    reporting = data.get("reporting", {})
    poll_matching = data.get("poll_matching", {})

    default_limit = _read_limit(respondents.get("default"), (500, 6000))
    limits = {
        method_key: _read_limit(respondents.get(method_key), default)
        for method_key, default in DEFAULT_RESPONDENT_LIMITS.items()
    }

    return ValidationConfig(
        sum_tolerance=float(data.get("sum", {}).get("tolerance", 2.0)),
        jump_threshold=float(data.get("jump", {}).get("threshold", 4.0)),
        respondent_limits=limits,
        respondent_default=default_limit,
        core_parties=CorePartyConfig(
            green_from_year=int(core_parties.get("green_from_year", 1990)),
            afd_from_year=int(core_parties.get("afd_from_year", 2014)),
            fdp_until_year=int(core_parties.get("fdp_until_year", 2021)),
        ),
        reporting=ReportingConfig(
            min_valid_share=float(reporting.get("min_valid_share", 0.90)),
            max_warning_share=float(reporting.get("max_warning_share", 0.10)),
            max_invalid_share=float(reporting.get("max_invalid_share", 0.05)),
        ),
        poll_matching=PollMatchingConfig(
            date_window_days=int(poll_matching.get("date_window_days", 7)),
            primary_provider=str(poll_matching.get("primary_provider", "wahlrecht.de")),
            secondary_provider=str(poll_matching.get("secondary_provider", "DAWUM")),
            result_parties=tuple(poll_matching.get("result_parties", ["SPD", "AFD"])),
            max_party_delta=float(poll_matching.get("max_party_delta", 1.0)),
            max_total_delta=float(poll_matching.get("max_total_delta", 1.5)),
            survey_date_tolerance_days=int(poll_matching.get("survey_date_tolerance_days", 0)),
            respondent_tolerance=int(poll_matching.get("respondent_tolerance", 0)),
            min_score_gap=float(poll_matching.get("min_score_gap", 0.01)),
        ),
    )


def _load_toml(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("rb") as file:
        return tomllib.load(file)


def _read_limit(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return default
    return int(value[0]), int(value[1])
