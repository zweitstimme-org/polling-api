# Polling API Worker Handoff Guide

This document is the short course a new worker (or LLM) needs to operate against the refactored FastAPI service in this repository. It explains how the application is put together, how the database schema is shaped, and the integration points you are expected to use.

## 1. Runtime & Project Layout
- **FastAPI application**: `app/main.py` instantiates the API and wires routers for ingestion, data export, webhooks, and election metadata. CORS is fully open for now.
- **Synchronous & async DB access**: `app/database.py` configures SQLAlchemy engines/sessions from `DATABASE_URL` and `ASYNC_DATABASE_URL`. Defaults point at a local Postgres instance (`postgresql+psycopg://postgres:postgres@localhost:5432/pollingapi_dev`).
- **Schema definitions**: ORM models live in `app/models.py`, while the request/response Pydantic models are in `app/schemas.py`.
- **Scripts**: `scripts/init_db.py` creates the schema using SQLAlchemy metadata. Run it after bringing up Postgres.
- **Data files**: Artifacts exposed by download endpoints/webhooks are stored under `./data`. The repo includes helper utilities that fetch, scrape, or refresh these files.
- **Environment variables**: See `.env` (not committed) plus defaults in code. The worker must at least provide `DATABASE_URL` if it is not running inside the docker-compose network.

### Key directories
| Path | Purpose |
| --- | --- |
| `app/routers/` | FastAPI routers grouped by purpose (`polls`, `download`, `database_insert`, `hook_*`). |
| `app/utils/` | Helper modules for scraping Bundestag results, election dates, notifying via ntfy, pulling DB snapshots, and fetching release assets. |
| `data/` | Output/ingested JSON, CSV, Parquet, and SQLite snapshots consumed by several endpoints. |
| `scripts/` | CLI utilities such as database initialization. |
| `static/` | Front-end assets if needed by future clients (currently unused by the API). |

## 2. Request Lifecycle
1. A client (your worker) calls `POST /ingest/polls` with a batch payload matching `app/schemas.RawPollBatchIn`.
2. The handler in `app/routers/database_insert.py` uses the async SQLAlchemy session to insert each poll into `polls_raw` and returns the new primary keys. Party dictionaries are automatically JSON-serialized before insertion.
3. Downstream cleaners/ETL jobs (not part of this repo yet) are expected to populate the normalized tables (`polls`, `poll_results`, etc.) based on `polls_raw`.
4. Clients can read back raw data via `GET /polls/raw` or download pregenerated files from `/polls/export/*`.

## 3. Database Schema Summary
All tables are created via `Base.metadata.create_all()` in `scripts/init_db.py`. The important pieces for ingestion/worker coordination are:

### `polls_raw`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `Integer` PK | Auto-increment primary key. |
| `publish_date`, `survey_date_start`, `survey_date_end` | `String` | Stored as received; downstream jobs convert to real dates. |
| `parties` | `Text` | JSON string with party → percentage mappings. Worker may send either dict or string. |
| `institute_id`, `forecast_provider`, `scope`, `election_id`, `method_id`, `Befragte`, `Zeitraum`, `forecast_provider`, `source` | `String` | Optional metadata captured as-is. `source` is the only required field. |
| `date_downloaded` | `String` | Free-form timestamp supplied by worker. |
| `inserted_at` | `DateTime` | Auto-populated with `datetime.utcnow()`.

### Normalized tables (populated later)
- **`polls`**: Cleansed poll records with FK links into lookup tables. Uniquely references one `polls_raw` row via `raw_id`.
- **`poll_results`**: Party-level results with a uniqueness constraint on `(poll_id, party_id)`.
- **`institutes`, `parties`, `forecast_providers`, `elections`, `methods`**: Lookup tables referenced by `polls`.

> **Note for worker authors**: The only table you need to touch is `polls_raw`. Keep payloads consistent so the normalization job can map them correctly.

## 4. Ingestion Contract (`POST /ingest/polls`)
- **Endpoint**: Mounted by `app/routers/database_insert.py` at `/ingest/polls`.
- **Auth**: Currently open; no token/secret required.
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
- **Response**: `{ "inserted": <count>, "record_ids": [<int>, ...] }`.
- **Edge cases**:
  - Empty batches return `{"inserted": 0, "record_ids": []}` without hitting the database.
  - If you pre-serialize `parties` as a JSON string it is stored verbatim; otherwise the API encodes it for you.
  - SQL errors are surfaced as `400` responses with the original DB error message.

### Worker checklist
1. Validate or coerce dates to ISO strings (`YYYY-MM-DD`) before sending.
2. Supply a stable `source` value so deduplication/ETL can partition feeds later.
3. Include the original source metadata (`institute_id`, `method_id`, etc.) whenever available; missing fields may limit downstream joins.
4. If you run multiple batches, you can parallelize requests—the endpoint opens a transaction per request and commits after the loop.
5. Handle retryable failures (network/HTTP 5xx) with exponential backoff; `400` means your payload is malformed.

## 5. Other API Surfaces Your Worker Should Know About
- `GET /polls/raw`: Returns the current contents of `polls_raw` ordered by `id`. Useful for smoke checks after ingestion.
- `GET /polls/`: Serves the `data/polls.json` snapshot (if present). This is not directly connected to the live database.
- `GET /polls/export/{json|csv|sqlite|parquet}`: File downloads for various prebuilt snapshots. The `data` directory must contain the respective files; generating them is outside the scope of the ingestion worker.
- `POST /webhook/scrape`, `POST /webhook/dates`, `POST /webhook/hook_db`: Protected by the `X-Secret: supersecret` header. They trigger background tasks in `app/utils/*` to refresh auxiliary datasets and send ntfy notifications.

## 6. Utilities & Background Tasks
- **Bundestag scraper (`app/utils/bundestag_scraper.py`)**: Fetches Bundestag historical election results and saves them as `data/bundestagswahl.json`.
- **Election date scraper (`app/utils/election_date.py`)**: Pulls the German election calendar into `data/election_dates.json`, marking estimated dates.
- **GitHub release fetcher (`app/utils/data_fetcher.py`)**: Downloads release assets from a private GitHub repo. Requires `GITHUB_TOKEN` and `GITHUB_REPO` environment variables.
- **Notifier (`app/utils/notifier.py`)**: Sends async notifications to `ntfy.sh/zweitstimme_org`. Webhooks rely on this to log success/failure.
- **DB pull stub (`app/utils/pull_db.py`)**: Placeholder for downloading the latest SQLite/Postgres dump. Worker authors should not rely on it yet; implementers still need to finish it.

## 7. Local Development & Testing
1. `uv sync` (Python 3.13) to install dependencies.
2. `docker compose up db` to start Postgres using `compose.yaml` definitions.
3. `uv run python scripts/init_db.py` to create tables.
4. `uv run fastapi dev app/main.py` to launch the API with hot reload.
5. Use `.env` to override `DATABASE_URL`, `GITHUB_TOKEN`, `GITHUB_REPO`, etc.

### Database inspection helpers
- Run `psql` against `pollingapi_dev` to inspect tables after ingestion.
- Use `uv run python -m app.scripts.dump_raw` (if you add such scripts) to debug payloads. Currently there is no built-in dump script beyond the API endpoints listed above.

## 8. Handoff Notes for the Next Worker Implementation
- Mirror the input schema defined in `app/schemas.RawPollIn` to stay forward-compatible with future validation upgrades.
- Plan for an eventual auth/token check on ingestion. `app/auth.py` contains a token verifier used elsewhere; expect `/ingest/polls` to adopt it later.
- The normalization layer (`polls`, `poll_results`, etc.) is not yet automated. If your worker expects those tables to reflect raw inserts immediately, you must run the cleaning job yourself or wait for future updates.
- The `/webhook/*` routes are intended for platform automation (scrapers, DB refresh). If your worker is replacing an older implementation, preserve the `X-Secret` header logic so existing infrastructure keeps functioning.
- `app/utils/pull_db.py` is a no-op. If your worker depended on a DB download hook, coordinate with this repo to implement it before calling `/webhook/hook_db`.

With this context, you should be able to adapt the worker to emit batches that the FastAPI ingestion endpoint accepts, monitor inserts via `/polls/raw`, and leave the rest of the system unchanged.
