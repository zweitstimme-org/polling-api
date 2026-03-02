# pollingapi

All-in-one solution for German election polling data by zweitstimme.org.

## Overview

pollingapi provides scraping, cleaning, and API endpoints for German election polling data. It aggregates polling data from multiple sources (Wahlrecht.de, DAWUM API) and exposes a normalized dataset via REST API.

## Status

**Pre-deployment.** This API is being prepared for production deployment.

## Quick Start

```bash
# Install dependencies
uv sync

# Initialize database
pollingapi db:init
pollingapi db:seed

# Run full pipeline (scrape + clean)
pollingapi pipeline:run

# Start API server
pollingapi server:start
```

The API will be available at `http://localhost:8000`

## CLI Commands

### Database

```bash
pollingapi db:init               # Initialize database tables
pollingapi db:seed               # Seed reference tables from JSON
pollingapi db:tables             # List tables with row counts
pollingapi db:ping               # Verify database connectivity
pollingapi db:reset --confirm    # Reset database (destructive)
pollingapi election-dates:update # Update state election dates from Wahlrecht.de Landtage
pollingapi export:all            # Export to JSON, CSV, Parquet
```

### Scrapers

```bash
pollingapi scraper:run <worker>   # Run specific scraper (e.g., forsa, bayern, all)
pollingapi scraper:list           # List available scrapers
pollingapi scraper:status         # Show scraper run status
```

**Note:** Run `pollingapi db:init` before the first scrape so the `polls_raw` table exists; otherwise inserts will fail with "no such table: polls_raw".

Options:
- `--debug, -d` - Enable debug logging
- `--dry-run, -n` - Run without inserting to database
- `--force, -f` - Force run (ignore initial run markers)

**State (Land) scrapers:** The scraper discovers and scrapes every valid table on each state page (current and historical periods). Logs show "table 1 of N", etc. When the site adds a new table (e.g. a new election period), it is scraped automatically—no config change needed.

### Pipeline

```bash
pollingapi pipeline:run           # Run full pipeline (scrape + clean)
pollingapi pipeline:clean          # Run cleaning only
pollingapi pipeline:inspect <id>   # Inspect raw poll cleaning
```

Options:
- `--dawum/--no-dawum` - Include/exclude DAWUM API (default: included)
- `--wahlrecht/--no-wahlrecht` - Run Wahlrecht.de scrapers (default: yes). Use `--no-wahlrecht` when wahlrecht.de is down to still get DAWUM data.
- `--skip-clean` - Skip cleaning step

### Server

```bash
pollingapi server:start            # Start API server (development)
pollingapi server:prod             # Start with Gunicorn (production)
pollingapi deploy:start            # Start server first, then run pipeline + export (for Render)
```

Options for `server:start`: `--host`, `--port`, `--reload`.  
Options for `deploy:start`: same as `server:prod` plus `--pipeline/--no-pipeline`, `--export/--no-export`, `--dawum/--no-dawum`, `--wahlrecht/--no-wahlrecht`. Use `--no-wahlrecht` when wahlrecht.de is down to still run DAWUM and get polls.

### Logs

```bash
pollingapi logs:view                # View log files
pollingapi logs:list                # List available logs
```

Options:
- `--file, -f` - Log file (zweitstimme, scraper, errors)
- `--lines, -n` - Number of lines (default: 50)
- `--follow, -F` - Follow log output

## Deployment (Render)

The **build** command (e.g. `uv sync`) only installs dependencies; it does **not** run the app or any scrapers. Only the **start** command runs your app and any pipeline/clean/export steps.

On a fresh deploy, the app runs `db:init` and `db:seed` only (from your start command). That populates **reference tables** (institutes, methods, parties, taskers, elections) but **no polls**—scrapers and the cleaner are not run automatically.

**Recommended (scrape + clean + export on start):** Use **`deploy:start`** so the server starts first (port open for Render), then the **full pipeline** runs (scrape → raw, then clean → polls and poll_results), then **export:all** (download files: JSON, CSV, Parquet). Use a **1GB** instance so the pipeline doesn't run out of memory.

```bash
uv run pollingapi db:init && uv run pollingapi db:seed && uv run pollingapi deploy:start -h 0.0.0.0 -p $PORT
```

**Alternative (512MB, no scrape on start):** Run only the **cleaner** so existing raw rows become polls; scrape elsewhere (cron/worker):

```bash
uv run pollingapi db:init && uv run pollingapi db:seed && uv run pollingapi deploy:start -h 0.0.0.0 -p $PORT --no-pipeline --clean --no-export
```

That starts the server, then runs **`pipeline:clean`** (raw → polls; no scrape). Scrape must run elsewhere (cron, worker) to fill `polls_raw`; then each start (or a scheduled clean) processes them into `polls`.

To skip pipeline/export and only start the server, use `--no-pipeline --no-export` or use `server:prod` directly.

**Memory:** The API itself is light (a few hundred polls, no heavy processing)—**512MB is plenty** for serving. The pipeline is tuned to use less RAM (DAWUM inserts in batches of 500; the cleaner processes raw polls in batches of 500). You may be able to run the **full pipeline** (scrape + clean + export) on **512MB** now; if it still OOMs, use **1GB** or run with `--no-pipeline` and run the pipeline elsewhere. With `PORT` set, the server uses **1 worker**.

If you run with `--no-pipeline`, the API will serve data from the database—but the DB is only filled when the pipeline runs. Run **`pollingapi pipeline:run`** (and optionally **`pollingapi export:all`**) on a schedule or separate worker that uses the **same database** (`DATABASE_URL`); then the web API will have polls to serve.

**If `/v1/raw-polls` has data but `/v1/polls` is empty:** the cleaning step hasn't run. Either add **`--clean`** to the start command (e.g. `deploy:start --no-pipeline --clean`) so the cleaner runs on every start, or run **`pollingapi pipeline:clean`** once (Render Shell, cron, or locally with the same `DATABASE_URL`).


**Download endpoints** (`/v1/download/json`, `/v1/download/csv`, etc.) serve only **pre-generated files** from `export:all`. If a file is missing, the API returns **404** (no on-the-fly generation).

## Raw vs cleaned data

**Raw polls** (`polls_raw`) store exactly what scrapers return. **Source** is the technical origin (e.g. `api`, `html_scraper`). **Provider** is always stored and reported (e.g. Wahlrecht.de, DAWUM)—use provider, not source, to distinguish data origin.

**Cleaned polls** (`polls`) are normalized and deduplicated. The cleaner copies (and normalizes) these from raw:

| Raw field           | Cleaned field        | Notes |
|--------------------|----------------------|--------|
| publish_date       | publish_date         | Normalized to date |
| survey_date_*      | survey_date_start / survey_date_end | **Field period** (always reported when we have it) |
| respondents        | respondents          | **Always reported** when raw has a number (parsed or fallback) |
| institute_id       | institute_id (FK)    | Mapped via `institutes.json` |
| provider           | provider_id (FK)     | **Always reported** (provider_id + provider_name in API) |
| method_id / hint   | method_id (FK)       | From raw or parsed from respondents |
| scope              | scope                | Canonical scope |
| source             | source               | Preserved (generic: api, html_scraper) |
| parties (JSON)     | poll_results         | Party IDs + percentages |

Raw-only fields kept for auditing: `institute_raw`, `zeitraum`, `tasker`, `election_id`, `date_downloaded`. API responses always include **provider** (id + name), **survey_date_start** / **survey_date_end** (field period), and **respondents** when we have them.

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Required variables:
- `API_SECRET` - Secret key for API authentication (change in production)

## Election dates (state elections)

State election dates („Nächster Wahltermin“) are taken from the [Wahlrecht.de Landtage overview](https://www.wahlrecht.de/umfragen/landtage/). Update them with:

```bash
pollingapi election-dates:update
```

- **Fixed dates** (e.g. „8. März 2026“, „20. September 2026“) are stored as given; the API returns `date_is_estimated: false`.
- **Seasonal terms** (Herbst, Frühjahr, Winter, Sommer + year) are converted to a representative mid-period date (e.g. Herbst 2028 → 2028-10-15) and returned with `date_is_estimated: true`.

The **elections** API (`GET /v1/elections`, `GET /v1/elections/{id}`) includes `election_date` (ISO date or null) and `date_is_estimated` (boolean) so clients can distinguish fixed election days from estimated windows.

If your database was created before this feature, add the new column (e.g. SQLite: `ALTER TABLE elections ADD COLUMN date_is_estimated BOOLEAN DEFAULT 0;`) or run `db:init --force` to recreate tables (destructive).

## API Endpoints

See `GET /docs` for complete API documentation. Main endpoints:
- `GET /` - API info
- `GET /health` - Health check
- `GET /polls/` - Polls data
- `GET /elections/` - Election summaries (includes `election_date`, `date_is_estimated`)
- `GET /raw/` - Raw poll data
- `GET /download/*` - File downloads
- `GET /dict/*` - Reference dictionaries

## Project Structure

```
pollingapi/
├── src/pollingapi/
│   ├── main.py              # FastAPI application
│   ├── cli.py               # CLI entry point
│   ├── database.py          # Database configuration
│   ├── database_seed.py     # JSON-based database seeding
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic schemas
│   ├── logging_config.py    # Logging configuration
│   ├── core/                # Core settings
│   ├── api/                 # API routers
│   │   ├── polls.py
│   │   ├── dictionaries.py
│   │   ├── download.py
│   │   └── elections.py
│   ├── scraper/             # Web scrapers
│   │   ├── base.py
│   │   ├── runner.py
│   │   ├── wahlrecht.py
│   │   ├── dawum.py
│   │   ├── config.py
│   │   ├── context.py
│   │   ├── snapshots.py
│   │   └── workers/         # Scraper worker configs
│   │       ├── sites_bund/ # Federal election scrapers
│   │       └── sites_land/ # State election scrapers
│   └── cleaner/             # ETL pipeline
│       ├── etl_pipeline.py
│       ├── json_mappings.py
│       ├── pipeline.py
│       ├── steps/           # Cleaning steps
│       └── transforms/       # Data transformations
├── json/                    # Reference data (institutes, parties, etc.)
├── data/                    # Database and exports
├── tests/
├── justfile
└── pyproject.toml
```

## Development

```bash
# Lint
ruff check .

# Type check
mypy .

# Test
pytest
```
