"""Configuration for data validation checks."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pollingapi.core import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "validation.toml"
PUBLIC_POLICY_PATH = PROJECT_ROOT / "public_policy.yaml"


@dataclass(frozen=True)
class CorePartyRule:
    """Expected parties for a scope group and optional year range."""

    scope: str
    parties: tuple[str, ...]
    from_year: int | None = None
    to_year: int | None = None


@dataclass(frozen=True)
class CorePartyPresencePolicy:
    """Context rules for deciding if a missing core party blocks publication."""

    enabled: bool = True
    min_comparison_polls: int = 5
    window_days: int = 365
    min_presence_share: float = 0.80


@dataclass(frozen=True)
class CorePartyConfig:
    """Scope/year rules for expected core parties."""

    rules: tuple[CorePartyRule, ...] = ()
    presence_policy: CorePartyPresencePolicy = field(default_factory=CorePartyPresencePolicy)


@dataclass(frozen=True)
class ReportingConfig:
    """Thresholds for validation reporting and health status."""

    min_valid_share: float = 0.90
    max_warning_share: float = 0.10
    max_invalid_share: float = 0.05


@dataclass(frozen=True)
class PublicDatasetSelectionConfig:
    """Source-selection policy for the public default API dataset."""

    cutoff_year: int = 2005
    pre_cutoff_provider: str = "Kayser/Rehmert"
    post_cutoff_provider: str = "wahlrecht.de"
    secondary_provider: str = "DAWUM"
    include_unmatched_secondary_after_cutoff: bool = True
    exclude_ambiguous_secondary: bool = True


@dataclass(frozen=True)
class PublicDatasetConfig:
    """Validation policy for the public default API dataset."""

    require_persisted_validation: bool = True
    include_valid: bool = True
    include_warnings: bool = True
    required_checks: tuple[str, ...] = ()
    exclude_failed_checks: tuple[str, ...] = ()
    selection: PublicDatasetSelectionConfig = field(default_factory=PublicDatasetSelectionConfig)


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
    public_dataset: PublicDatasetConfig
    poll_matching: PollMatchingConfig


DEFAULT_RESPONDENT_LIMITS = {
    "TELEFONISCH": (700, 4000),
    "ONLINE": (500, 6000),
    "TELEFON_ONLINE": (700, 4000),
    "PERSOENLICH": (500, 3000),
    "UNBEKANNT": (500, 6000),
}


@lru_cache
def get_validation_config(
    config_path: Path = CONFIG_PATH,
    public_policy_path: Path = PUBLIC_POLICY_PATH,
) -> ValidationConfig:
    """Load validation config from TOML plus optional public_policy.yaml overrides."""
    data = _load_toml(config_path)
    policy = _load_yaml(public_policy_path)
    respondents = data.get("respondents", {})
    core_parties = _merged_section(data, policy, "core_parties")
    reporting = data.get("reporting", {})
    public_dataset = _merged_section(data, policy, "public_dataset")
    public_selection = public_dataset.get("selection", {})
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
        core_parties=_read_core_party_config(core_parties),
        reporting=ReportingConfig(
            min_valid_share=float(reporting.get("min_valid_share", 0.90)),
            max_warning_share=float(reporting.get("max_warning_share", 0.10)),
            max_invalid_share=float(reporting.get("max_invalid_share", 0.05)),
        ),
        public_dataset=PublicDatasetConfig(
            require_persisted_validation=bool(
                public_dataset.get("require_persisted_validation", True)
            ),
            include_valid=bool(public_dataset.get("include_valid", True)),
            include_warnings=bool(public_dataset.get("include_warnings", True)),
            required_checks=tuple(public_dataset.get("required_checks", [])),
            exclude_failed_checks=tuple(public_dataset.get("exclude_failed_checks", [])),
            selection=PublicDatasetSelectionConfig(
                cutoff_year=int(public_selection.get("cutoff_year", 2005)),
                pre_cutoff_provider=str(
                    public_selection.get("pre_cutoff_provider", "Kayser/Rehmert")
                ),
                post_cutoff_provider=str(
                    public_selection.get("post_cutoff_provider", "wahlrecht.de")
                ),
                secondary_provider=str(public_selection.get("secondary_provider", "DAWUM")),
                include_unmatched_secondary_after_cutoff=bool(
                    public_selection.get("include_unmatched_secondary_after_cutoff", True)
                ),
                exclude_ambiguous_secondary=bool(
                    public_selection.get("exclude_ambiguous_secondary", True)
                ),
            ),
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


def _load_yaml(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{config_path} must contain a mapping at the top level")
    return data


def _merged_section(
    base: dict[str, Any],
    override: dict[str, Any],
    section: str,
) -> dict[str, Any]:
    merged = dict(base.get(section, {}))
    merged.update(override.get(section, {}))
    return merged


def _read_limit(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return default
    return int(value[0]), int(value[1])


def _read_core_party_config(data: dict[str, Any]) -> CorePartyConfig:
    rules = data.get("rules")
    if not rules:
        rules = [
            {"scope": "federal", "parties": ["CDU_CSU", "SPD", "FDP"]},
            {"scope": "state", "parties": ["CDU", "SPD", "FDP"]},
            {"scope": "by", "parties": ["CSU", "SPD", "FDP"]},
            {"scope": "federal", "parties": ["GRUENE"], "from_year": 1990},
            {"scope": "state", "parties": ["GRUENE"], "from_year": 1990},
            {"scope": "by", "parties": ["GRUENE"], "from_year": 1990},
            {"scope": "*", "parties": ["AFD"], "from_year": 2014},
        ]

    policy = data.get("presence_policy", {})
    return CorePartyConfig(
        rules=tuple(_read_core_party_rule(rule) for rule in rules),
        presence_policy=CorePartyPresencePolicy(
            enabled=bool(policy.get("enabled", True)),
            min_comparison_polls=int(policy.get("min_comparison_polls", 5)),
            window_days=int(policy.get("window_days", 365)),
            min_presence_share=float(policy.get("min_presence_share", 0.80)),
        ),
    )


def _read_core_party_rule(rule: dict[str, Any]) -> CorePartyRule:
    return CorePartyRule(
        scope=str(rule.get("scope", "*")),
        parties=tuple(str(party) for party in rule.get("parties", [])),
        from_year=_optional_int(rule.get("from_year")),
        to_year=_optional_int(rule.get("to_year")),
    )


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
