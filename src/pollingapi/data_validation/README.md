# Data Validation

This package validates cleaned poll data without changing the source poll rows.

The validation reads from `polls` and `poll_results`, wich are the cleaned polls. When validation is run with
`--persist`, the results are written to the separate `poll_validations` table.
This keeps the cleaned polling data unchanged while still making validation
results easy to query.

## Commands

Run validation without writing to the database:

```bash
uv run pollingapi validation:run
```

Run validation and store results in `poll_validations`:

```bash
uv run pollingapi validation:run --persist
```

Inspect one persisted validation result:

```bash
uv run pollingapi validation:inspect C00000001
```

Show an aggregate quality report:

```bash
uv run pollingapi validation:report
```

The full pipeline also runs validation automatically:

```bash
uv run pollingapi pipeline:run
```

In the pipeline, validation runs after cleaning and before export.

## Files

- `service.py` runs the validation checks and optionally stores the result.
- `report.py` builds aggregate reports from persisted validation rows.
- `config.py` loads thresholds from `validation.toml` in the project root.
- `validate_*.py` files contain the individual checks.

## Stored Data

Validation results are stored in `poll_validations`. The table has one row per
cleaned poll and links back to `polls` through `poll_id`.

The main check columns use a `qc_` prefix:

- `qc_party_percentage_range`
- `qc_result_sum_check`
- `qc_date_consistency`
- `qc_respondents_plausible`
- `qc_core_parties_present`
- `qc_institute_result_jump`
- `qc_scope_result_jump`

The table also stores `valid`, error and warning counts, the validation time,
and a JSON `details` payload with the full check output.

`pipeline_runs` stores a compact validation summary for each pipeline run:

- validation status
- total validated polls
- valid, invalid, and warning counts
- valid share

## Configuration

Thresholds and limits are configured in `validation.toml` at the project root.
This includes the sum tolerance, jump threshold, respondent limits, core-party
year rules, and report health thresholds.

The reporting thresholds decide whether validation quality is `pass`, `warn`,
or `fail`:

```toml
[reporting]
min_valid_share = 0.90
max_warning_share = 0.10
max_invalid_share = 0.05
```

The public v2 dataset is also configured in `validation.toml`:

```toml
[public_dataset]
require_persisted_validation = true
include_valid = true
include_warnings = true
exclude_failed_checks = []
```

With these defaults, `/v2/polls` and `/v2/poll-results` include polls that have
a persisted validation row and pass all error-severity checks. Warning rows are
included. Set `include_warnings = false` to remove warning rows from the public
dataset, or add validation check column names to `exclude_failed_checks` to
exclude rows that fail specific checks.

## API

Persisted validation can be inspected through:

```text
GET /v1/polls/{poll_identifier}/validation
```

The aggregate report is available through:

```text
GET /v1/validation/report
```

The health endpoints also include a compact `validation:quality` check:

```text
GET /health
GET /heartbeat
```

## Alerts

Slack and ntfy notifications include the validation summary from the pipeline
run. If validation status is `warn` or `fail`, the notification shows the
validation status, valid share, invalid count, warning count, and the top
failing checks.

Validation warnings do not fail the pipeline by themselves. They are reported
as quality alerts so the data source and pipeline run remain separate from the
quality assessment.
