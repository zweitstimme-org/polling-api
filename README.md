# polling-api

FastAPI service that ingests German polling data, stores the raw payloads in Postgres, and exposes download/export endpoints for downstream consumers. A hosted test deployment with interactive docs lives at https://api.fasttrack29.com/docs.

## Features
- `POST /ingest/polls` accepts batches of raw polls and persists them to the `polls_raw` table via SQLAlchemy.
- Read endpoints serve cleaned JSON (`GET /polls`) and raw data via file/streaming paths under `/raw`.
- File exports stream pre-generated snapshots from the `data/` directory (JSON, CSV, SQLite, Parquet).
- Startup bootstrap automatically ensures the configured Postgres database exists and applies metadata.
- Optional data fetcher downloads the latest release assets from a private GitHub repo to refresh `data/`.

## Requirements
- Python 3.13 with [uv](https://github.com/astral-sh/uv) installed
- Docker + Docker Compose (for Postgres and/or running the API in containers)
- Local `.env` providing database credentials and optional API metadata (see below)

## Local Development
1. **Install dependencies**
   ```bash
   uv sync
   ```
2. **Create `.env`** (example values match `compose.yaml`):
   ```bash
   cat <<'ENV' > .env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/pollingapi_dev
   ASYNC_DATABASE_URL=${DATABASE_URL}
   API_TITLE=Zweitstimme Polling API
   API_VERSION=0.0.1
   API_DESCRIPTION=The one stop API for German elections.
   GITHUB_TOKEN=
   GITHUB_REPO=
   ENV
   ```
3. **Start Postgres**
   ```bash
   docker compose up db
   ```
4. **Create/upgrade the schema**
   ```bash
   uv run python scripts/init_db.py
   ```
5. **Run the API** (reload + auto-watch):
   ```bash
   uv run fastapi dev app/main.py
   ```
6. Visit http://localhost:8000/docs for interactive API docs; `/health` returns a simple status payload.

### Docker Compose Dev Stack
Instead of running the API directly, use the dev compose file which mounts your working tree and keeps a persistent uv virtualenv:
```bash
docker compose -f dev.compose.yaml up --build
```
This brings up the Postgres service, runs a one-shot `db-init` job to apply the `app/models.py` metadata, and then starts the API with automatic restarts. The production-style manifest is `compose.yaml` and uses `fastapi run` inside the container image.

### Collect polls via pollv (CLI container)
The poll scraper CLI is built into the `poll-vault` image but exposed as `pollv`. Bring up the usual dev stack (DB, db-init, API) as above, then run the scraper ad hoc using the `scraper` profile:
```bash
# start db + api (if not already running)
docker compose -f dev.compose.yaml up -d db db-init api

# trigger the scraper (image entrypoint runs `uv run --frozen pollv`, we pass `run-all`)
docker compose -f dev.compose.yaml run --rm pollv run-all
```
The scraper container exits after completion and does not auto-restart.

### Data-cleaner CLI via docker compose
The `data-cleaner` service in `dev.compose.yaml` points the CLI image at the dev database and mounts `./data/export` to `/app/data/export` (shared with the API container). The default command runs `db export --output-dir /app/data/export --format json`, producing `polls.json`, `poll_results.json`, and `raw_polls.json` inside `data/export/` on the host:
```bash
# one-shot export (default command)
docker compose -f dev.compose.yaml run --rm data-cleaner

# other commands (override the command as needed)
docker compose -f dev.compose.yaml run --rm data-cleaner db ping
docker compose -f dev.compose.yaml run --rm data-cleaner db init
docker compose -f dev.compose.yaml run --rm data-cleaner db seed
docker compose -f dev.compose.yaml run --rm data-cleaner db tables
docker compose -f dev.compose.yaml run --rm data-cleaner db polls-head --limit 50
docker compose -f dev.compose.yaml run --rm data-cleaner db export-raw --output-path /data/export/polls_raw.json
docker compose -f dev.compose.yaml run --rm data-cleaner pipeline process-new
docker compose -f dev.compose.yaml run --rm data-cleaner pipeline inspect 123   # replace 123 with polls_raw.id
docker compose -f dev.compose.yaml run --rm data-cleaner party-mapping
```
Ensure `db` and `db-init` are up before commands that read or write tables.

### Daily export helper (exclude raw polls)
Export all tables except `polls_raw` to a JSON file (default `data/daily_export.json`):
```bash
uv run python scripts/export_daily.py
# or choose a different path:
uv run python scripts/export_daily.py --output data/export-$(date +%F).json
```
The script uses `DATABASE_URL` from your `.env`. Output directories are created automatically.

## Environment Variables
| Name | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | Sync SQLAlchemy engine string | `postgresql+psycopg://postgres:postgres@localhost:5432/pollingapi_dev` |
| `ASYNC_DATABASE_URL` | Async engine string used by ingestion router | Falls back to `DATABASE_URL` |
| `API_TITLE`, `API_VERSION`, `API_DESCRIPTION` | Customize FastAPI metadata | Hard-coded defaults in `app/main.py` |
| `GITHUB_TOKEN`, `GITHUB_REPO` | Needed by `app/utils/data_fetcher.py` to pull release assets into `data/` | unset |

## Database Schema
`app/models.py` defines both the ingestion table and the normalized tables that future ETL jobs will populate. Only `polls_raw` is written to by this API today:
- `polls_raw`: stores the JSON payload as received; `parties` is serialized as text and `inserted_at` is set automatically.
- `polls`, `poll_results`, `institutes`, `parties`, `forecast_providers`, `elections`, `methods`: currently empty shells that downstream cleaners will fill by referencing `polls_raw` rows.

Schema creation logic lives in `app/db_init.py` and is shared by the FastAPI startup hook and `scripts/init_db.py`.

## API Overview
### Ingest raw polls
- **Endpoint**: `POST /ingest/polls`
- **Body schema**:
  ```json
  {
    "polls": [
      {
        "source": "bundestag",
        "publish_date": "2024-04-25",
        "survey_date_start": "2024-04-20",
        "survey_date_end": "2024-04-23",
        "parties": {"CDU": 29.0, "SPD": 17.5},
        "Befragte": "1000",
        "scope": "national",
        "date_downloaded": "2024-04-25T12:00:00Z"
      }
    ]
  }
  ```
- **Response**: `{ "inserted": <count>, "record_ids": [<int>, ...] }`
- `parties` can be sent either as an object or a JSON string; the router normalizes it before insertion.

### Read/Download data
- `GET /polls` – serves `data/polls.json` for quick JSON consumption.
- `GET /raw` – serves the pre-generated raw export file (e.g., `data/export/polls_raw.json`).
- `GET /raw/stream` – streams the full `polls_raw` table as a JSON array in batches without loading everything into memory.
- `GET /raw/latest` – returns the newest 100 rows from `polls_raw`.
- `GET /polls/export/json|csv|sqlite|parquet` – streams files from the `data/` directory if present.
- `GET /polls/recent` – placeholder endpoint reserved for future weekly filtering.
- Additional routers (`/election/*`, `/hook_*`) are stubs for future integrations and may return `501` until implemented.

## Project Layout
| Path | Description |
| --- | --- |
| `app/main.py` | FastAPI application factory, CORS setup, router wiring, and startup DB bootstrap. |
| `app/database.py` | Sync + async SQLAlchemy engines/session factories. |
| `app/routers/` | Feature routers (`polls`, `download`, `database_insert`, `hook_*`, etc.). |
| `app/utils/` | Helper utilities for scraping, GitHub release downloads, notifications, etc. |
| `data/` | Working directory for JSON/CSV/SQLite/Parquet exports served by the API. |
| `scripts/init_db.py` | CLI helper to create the database and tables using the shared metadata. |
| `compose.yaml` / `dev.compose.yaml` | Container definitions for production vs. iterative development. |

## Maintenance Tips
- If downloads return 404, ensure the corresponding file exists in `./data` or run the GitHub `data_fetcher` utility after setting `GITHUB_TOKEN`/`GITHUB_REPO`.
- Any migration-like change (new columns/tables) should be reflected in `app/models.py` before rerunning `scripts/init_db.py`.
- Automated tests are not yet wired up; rely on `uv run fastapi dev app/main.py` locally plus linting/typing via `pyright` if installed.

Happy polling!
