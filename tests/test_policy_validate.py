"""Tests for public policy validation."""

from __future__ import annotations

from pollingapi.cli import _validate_public_policy


def test_validate_public_policy_accepts_valid_yaml(tmp_path) -> None:
    config_path = tmp_path / "validation.toml"
    policy_path = tmp_path / "public_policy.yaml"
    config_path.write_text("", encoding="utf-8")
    policy_path.write_text(
        """
public_dataset:
  required_checks:
    - qc_result_sum_check
  selection:
    cutoff_year: 2005
    pre_cutoff_provider: Kayser/Rehmert
    post_cutoff_provider: wahlrecht.de
    secondary_provider: DAWUM
core_parties:
  presence_policy:
    min_comparison_polls: 5
    window_days: 365
    min_presence_share: 0.8
  rules:
    - scope: federal
      parties: [SPD]
""",
        encoding="utf-8",
    )

    assert _validate_public_policy(config_path, policy_path) == []


def test_validate_public_policy_reports_unknown_values(tmp_path) -> None:
    config_path = tmp_path / "validation.toml"
    policy_path = tmp_path / "public_policy.yaml"
    config_path.write_text("", encoding="utf-8")
    policy_path.write_text(
        """
public_dataset:
  required_checks:
    - qc_missing_check
core_parties:
  presence_policy:
    min_comparison_polls: 0
    window_days: 0
    min_presence_share: 1.5
  rules:
    - scope: federal
      parties: [SPD, UNKNOWN]
      from_year: 2025
      to_year: 2024
""",
        encoding="utf-8",
    )

    errors = _validate_public_policy(config_path, policy_path)

    assert "public_dataset.required_checks has unknown check(s): qc_missing_check" in errors
    assert "core_parties.rules[1].parties has unknown party key(s): UNKNOWN" in errors
    assert "core_parties.rules[1].from_year must be less than or equal to to_year" in errors
    assert "core_parties.presence_policy.min_comparison_polls must be at least 1" in errors
    assert "core_parties.presence_policy.window_days must be at least 1" in errors
    assert (
        "core_parties.presence_policy.min_presence_share must be greater than 0 and at most 1"
        in errors
    )
