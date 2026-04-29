![zweitstimme.org](https://zweitstimme.org/images/logo_orange.png)


# polling-api

All-in-one pipeline and API for German election polling data by zweitstimme.org

## Project status

This repository currently documents and ships the **development/testing setup**.

- The API should be treated as a local development/test service for now.
- This guide is focused on running the stack locally on your machine.
- Production deployment details may evolve as the project stabilizes.

## What this project does

`polling-api` collects polling data from multiple sources, normalizes it into a consistent relational
model, exports machine-readable datasets, and serves the data through a FastAPI application.

The **main operational entrypoint** is:

```bash
uv run pollingapi pipeline:run
```

That command runs the full end-to-end process (all workers + cleaning + export + optional archive).

## Dataflow at a glance

```text
HTML workers + DAWUM API
          |
          v
      polls_raw (immutable source rows)
          |
          v
  ETL cleaning + JSON mappings
          |
          v
   polls + poll_results + reference tables
          |
          +--> export files in data/export/
          |
          +--> optional S3 archive zip + index
          |
          +--> FastAPI endpoints (/v1/*)
```

## Quick start (local dev)

```bash
# 1) install dependencies
uv sync

# 2) initialize schema + seed dictionaries
uv run pollingapi db:init
uv run pollingapi db:seed

# 3) run full pipeline (recommended main flow)
uv run pollingapi pipeline:run

# 4) start API locally
uv run pollingapi server:start --reload
```

Open:
- API docs: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- Heartbeat: `http://localhost:8000/health` (alias: `/heartbeat`)

This is the recommended way to explore and validate the current development version locally.

## Core commands

### Pipeline (main)

```bash
uv run pollingapi pipeline:run                 # Full run: scrape + clean + export + optional archive
uv run pollingapi pipeline:clean               # Clean only (from polls_raw into normalized tables)
uv run pollingapi pipeline:inspect <raw_id>    # Inspect one raw row
```

### Scrapers

```bash
uv run pollingapi scraper:list
uv run pollingapi scraper:run all
uv run pollingapi scraper:run forsa
uv run pollingapi scraper:status
```

### Database and exports

```bash
uv run pollingapi db:ping
uv run pollingapi db:tables
uv run pollingapi export:all
uv run pollingapi db:reset --confirm
```

### API server

```bash
uv run pollingapi server:start --host 0.0.0.0 --port 8000 --reload
uv run pollingapi server:prod --host 127.0.0.1 --port 8000
```

## API surface

The app mounts versioned routes under `/v1`.

- `GET /` basic API metadata
- `GET /health` and `GET /heartbeat` service heartbeat and run freshness
- `GET /v1/polls` cleaned, normalized polls (filters + pagination)
- `GET /v1/raw-polls` immutable raw scraped rows
- `GET /v1/results` flattened grouped results view
- `GET /v1/reference/*` lookup tables (institutes, parties, providers, methods, elections, taskers)
- `GET /v1/elections` election summaries and metadata
- `GET /v1/download/*` dataset downloads (json/csv/parquet/sqlite/raw/results)
- `GET /v1/archive` archive listing (HTML/JSON) when S3 is configured

## Health and observability

`/health` and `/heartbeat` return structured status including:
- overall service status
- current version/release id
- total poll count in the database
- last successful pipeline run timestamp
- time since last run in seconds
- component checks (`database:polls`, `pipeline:last_run`)

Pipeline runs are persisted in `pipeline_runs` for auditability and exposed through heartbeat freshness.

## Configuration

Copy `.env.example` and adjust as needed:

```bash
cp .env.example .env
```

Common variables:
- `DATABASE_URL`, `ASYNC_DATABASE_URL`
- `API_HOST`, `API_PORT`, `API_RELOAD`
- `SCRAPER_DELAY`, `SCRAPER_TIMEOUT`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`, `AWS_S3_REGION`,
  `AWS_S3_ENDPOINT_URL` (for archive upload)
- `NTFY_URL`, `SLACK_WEBHOOK_URL` (optional notifications after pipeline runs)

### Versioning

API version is read from the root file `.apiversion` and surfaced in OpenAPI and heartbeat responses.

## Project structure

```text
pollingAPI/
├── src/pollingapi/
│   ├── cli.py                    # Typer CLI entrypoint
│   ├── main.py                   # FastAPI app + /health + /heartbeat
│   ├── database.py               # Engine/session/init helpers
│   ├── models.py                 # SQLAlchemy models incl. PipelineRun
│   ├── api/                      # Routers mounted at /v1
│   │   ├── polls.py
│   │   ├── dictionaries.py
│   │   ├── elections.py
│   │   ├── download.py
│   │   └── data.py               # Archive endpoints
│   ├── scraper/                  # Worker discovery + source scrapers
│   │   ├── runner.py
│   │   ├── dawum.py
│   │   └── workers/
│   ├── cleaner/                  # ETL normalization pipeline
│   │   ├── etl_pipeline.py
│   │   ├── transforms/
│   │   └── steps/
│   └── services/s3.py            # Archive upload/listing
├── json/                         # DAWUM reference snapshots / source dictionaries
├── data/                         # SQLite DB, logs, exports
├── tests/
├── .apiversion
└── pyproject.toml
```

## Development workflow

```bash
# lint
uv run ruff check src/

# format
uv run ruff format src/

# type check
uv run mypy src/

# tests
uv run pytest tests/
```

## Notes

- `pollingapi` and `zweitstimme` are both installed CLI entrypoints.
- `pipeline:run` is designed for repeatable scheduled execution (cron/systemd/CI).
- Raw rows remain in `polls_raw`; normalization writes to `polls` and `poll_results`.
- Treat this README as a **local development guide** first; production hardening docs will follow.
