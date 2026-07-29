# Public Policy And Validation

This document explains how the public poll data is selected.

## Files

The public policy is in `public_policy.yaml`.

The base validation settings are in `validation.toml`.

The code loads `validation.toml` first. Then it loads `public_policy.yaml`.
Values in `public_policy.yaml` replace values with the same name in
`validation.toml`.

## Pipeline Step

The pipeline has this order:

1. Scrapers and importers write source data to `polls_raw`.
2. The cleaner writes normalized data to `polls` and `poll_results`.
3. Public selection marks cleaned polls with `is_public`.
4. Validation checks all cleaned polls.
5. The export and API apply the public policy.

The `is_public` value is not the complete public rule. It is only the first
selection step. The API and export also require the public policy.

## Validation

Validation checks each cleaned poll.

The checks are:

- `qc_party_percentage_range`
- `qc_result_sum_check`
- `qc_date_consistency`
- `qc_respondents_plausible`
- `qc_core_parties_present`
- `qc_institute_result_jump`
- `qc_scope_result_jump`

Each check has a pass state and a severity.

The public policy can set `required_checks`. If this list is set, a poll is
research-ready only when all checks in the list pass.

Today the required checks are:

- `qc_party_percentage_range`
- `qc_result_sum_check`
- `qc_date_consistency`
- `qc_respondents_plausible`
- `qc_core_parties_present`

Jump checks can add review notes. They do not remove a poll from the default
public data today.

Core-party checks use nearby polls. A missing party removes a poll from the
default public data only when that party is usually present in nearby polls for
the same scope.

If the party is also missing in enough nearby polls, the absence is accepted.
The check still adds a message and the affected party.

If there are not enough nearby polls, the absence is accepted. The check still
adds a message and the affected party.

## Public Policy

The public policy has two parts.

The `selection` section tells the cleaner which source is primary.

The `core_parties.presence_policy` section tells validation when a missing
monitored party is a blocking quality issue.

Current source selection:

- Before 2005, `Kayser/Rehmert` is the primary source.
- From 2005, `wahlrecht.de` is the primary source.
- `DAWUM` can be public when it does not match a primary-source poll.
- Ambiguous secondary-source matches are not public.

The public API and public export then apply this rule:

- The poll must have `is_public = true`.
- The poll must have a persisted validation row.
- The poll must be valid by the configured `required_checks`.
- Warning checks are allowed.
- Failed checks in `exclude_failed_checks` are not allowed.

One exception exists. Pre-2005 `Kayser/Rehmert` polls are treated as already
validated. They are cleaned and served without an extra validation block.

## Core-Party Presence Policy

The policy monitors configured parties for each scope.

Current presence policy:

- Use nearby polls in the same scope.
- Use polls within 365 days before or after the poll.
- Require at least 5 comparison polls.
- Treat a missing party as blocking when the party is present in 80 percent or
  more of comparison polls.

Example:

If `CDU` is present in 5 of 5 nearby Brandenburg polls, but missing in one
Brandenburg poll, that poll is not research-ready.

If `FDP` is missing in 5 of 5 nearby Brandenburg polls, another Brandenburg poll
without `FDP` stays research-ready.

This handles single extraction errors and also allows real long-term party
absence.

## Public Names

The public API uses English names.

Examples:

- `BUND` becomes `federal`.
- `EU_WAHLEN` becomes `european`.
- State election rows use `State election`.
- Federal election rows use `Federal election`.
- European election rows use `European election`.

Internal database values stay unchanged.

## Exports

The default export files are the same dataset that the public API serves.

Default files:

- `polls.json`
- `polls.csv`
- `polls.parquet`
- `polls_without_results.json`
- `polls_without_results.csv`
- `polls_without_results.parquet`
- `poll_results.json`
- `poll_results.csv`
- `poll_results.parquet`

The archive also contains complete cleaned dumps:

- `all_cleaned_polls.*`
- `all_cleaned_poll_results.*`
- `polls_raw.*`
- reference data
- validation config
- public policy
- validation report

The public files do not include internal routing fields such as `fingerprint`,
`is_public`, or `public_exclusion_reason`.

The complete cleaned dump keeps these fields for audit use.

## Needed Optimizations

No large optimization is needed now.

Useful small improvements are:

- Run `pollingapi policy:validate` in CI.
- Make the pre-2005 `Kayser/Rehmert` exception check the import source too.
- Add source-specific date and respondent rules if old sources need them.
- Add a report section for rows that `is_public` marks as public but the final
  public policy does not serve.

Do these only when they become a real source of bad data or unclear reports.
