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
class ValidationConfig:
    """Runtime configuration for data validation."""

    sum_tolerance: float
    jump_threshold: float
    respondent_limits: dict[str, tuple[int, int]]
    respondent_default: tuple[int, int]
    core_parties: CorePartyConfig


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
