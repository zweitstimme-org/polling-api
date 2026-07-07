# Data Importer

The importer loads external data files into `polls_raw`. It does not write
directly to the cleaned `polls` or `poll_results` tables. After raw rows are
inserted, the existing cleaner can process them through the same normalization
path used for scraper data.

This keeps one rule for all data sources:

```text
file import -> polls_raw -> cleaner -> polls + poll_results
```

## Directory Layout

Importer code lives in `src/pollingapi/importer`.

```text
src/pollingapi/importer/
├── formats/          # Low-level file readers
├── sources/          # Source-specific adapters
├── insertion.py      # RawPoll insert and dedupe logic
├── runner.py         # Top-level import orchestration
└── schemas.py        # Import models and result types
```

Data files should live in the top-level `imports/` directory:

```text
imports/
└── polling_data.csv
```

When a CLI command receives a relative file path, it resolves that path relative
to `imports/`. Absolute file paths are also supported.

## Import Sources

An import source converts one input file into rows that match the `polls_raw`
schema. The built-in source is `csv`, also available as `manual_csv`.

List available sources with:

```bash
uv run pollingapi import:list
```

The generic CSV source supports two styles for party results:

1. Party results as separate columns.
2. Party results as a JSON object in a `parties` or `results` column.

## CSV Format

A typical CSV can look like this:

```csv
publish_date,institut,scope,election_id,respondents,CDU/CSU,SPD,GRÜNE,FDP,AfD,Linke
2024-06-01,Forsa,Bund,Bundestagswahl,1000,30,16,13,5,18,3
```

The importer recognizes common aliases for the raw metadata fields. For example:

```text
publish_date: publish_date, datum, date, published_at
institute_id: institute_id, institut, institute
respondents: respondents, befragte, sample_size
scope: scope, state, land
election_id: election_id, election, election_type
method_id: method_id, method, survey_method
tasker: tasker, auftraggeber, commissioner
```

Columns that are not recognized as metadata are treated as party result columns.
Their names are preserved because the cleaner uses those names for party
normalization.

Alternatively, results can be provided as JSON:

```csv
publish_date,institut,scope,election_id,respondents,parties
2024-06-01,Forsa,Bund,Bundestagswahl,1000,"{""CDU/CSU"": ""30"", ""SPD"": ""16""}"
```

## Workflow

Put the file into `imports/`:

```text
imports/forsa_manual.csv
```

Preview how the importer parses it:

```bash
uv run pollingapi import:preview forsa_manual.csv
```

The preview command does not write to the database. It parses the file and shows
the raw rows that would be inserted.

Import the file into `polls_raw`:

```bash
uv run pollingapi import:run forsa_manual.csv
```

Import and immediately run the cleaner:

```bash
uv run pollingapi import:run forsa_manual.csv --clean
```

Use a specific source if needed:

```bash
uv run pollingapi import:run forsa_manual.csv --source csv --clean
```

Use a dry run to parse and dedupe without committing:

```bash
uv run pollingapi import:run forsa_manual.csv --dry-run
```

## What Gets Written

The importer writes `RawPoll` rows with fields such as:

```text
publish_date
survey_date_start
survey_date_end
respondents
zeitraum
parties
institute_id
provider
tasker
source
scope
election_id
method_id
worker
survey_type
date_downloaded
pipeline_run_id
```

For CSV imports, the default values are:

```text
source = csv_import
method_id = 99
worker = import:csv
date_downloaded = current timestamp, if not supplied
```

The `parties` field is stored as JSON text, matching the existing raw scraper
format.

## Deduplication

Before inserting a row, the importer checks whether an equivalent row already
exists in `polls_raw`. It also deduplicates repeated rows inside the same import
file.

The dedupe key includes the raw poll metadata and party payload:

```text
publish_date
survey_date_start
survey_date_end
respondents
zeitraum
parties
institute_id
provider
tasker
source
scope
election_id
method_id
worker
survey_type
```

If a row matches this key, it is skipped instead of inserted again.

## Cleaning Imported Data

Imported rows are cleaned by the existing ETL pipeline. The cleaner reads from
`polls_raw`, normalizes dates, respondents, institutes, methods, election scope,
and party names, and then writes to `polls` and `poll_results`.

You can run the cleaner as part of import:

```bash
uv run pollingapi import:run forsa_manual.csv --clean
```

Or run it separately:

```bash
uv run pollingapi pipeline:clean
```

Imported rows therefore follow the same rules as scraper rows. Unknown parties,
invalid dates, duplicate cleaned fingerprints, and other data quality concerns
are handled by the existing cleaner and validation logic.

## Adding a Source-Specific Importer

Use a source-specific importer when a file format needs custom parsing that the
generic CSV source should not own.

Add a new module in `src/pollingapi/importer/sources/` and implement
`ImportSource`:

```python
from pathlib import Path

from pollingapi.importer.schemas import RawPollImport
from pollingapi.importer.sources.base import ImportSource


class ExampleImportSource(ImportSource):
    name = "example"

    def load(self, path: Path) -> list[RawPollImport]:
        ...
```

Then register it in `src/pollingapi/importer/sources/__init__.py`.

The source should return `RawPollImport` objects. It should not insert database
rows itself and should not call the cleaner directly. The runner owns those
steps so all sources behave consistently.
