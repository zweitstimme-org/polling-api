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
pollingapi db:init           # Initialize database tables
pollingapi db:seed            # Seed reference tables from JSON
pollingapi db:tables          # List tables with row counts
pollingapi db:ping            # Verify database connectivity
pollingapi db:reset --confirm # Reset database (destructive)
pollingapi export:all         # Export to JSON, CSV, Parquet
```

### Scrapers

```bash
pollingapi scraper:run <worker>   # Run specific scraper (e.g., forsa, bayern, all)
pollingapi scraper:list           # List available scrapers
pollingapi scraper:status         # Show scraper run status
```

Options:
- `--debug, -d` - Enable debug logging
- `--dry-run, -n` - Run without inserting to database
- `--force, -f` - Force run (ignore initial run markers)

### Pipeline

```bash
pollingapi pipeline:run           # Run full pipeline (scrape + clean)
pollingapi pipeline:clean          # Run cleaning only
pollingapi pipeline:inspect <id>   # Inspect raw poll cleaning
```

Options:
- `--dawum/--no-dawum` - Include/exclude DAWUM API (default: included)
- `--skip-clean` - Skip cleaning step

### Server

```bash
pollingapi server:start            # Start API server
```

Options:
- `--host, -h` - Host to bind (default: 0.0.0.0)
- `--port, -p` - Port to bind (default: 8000)
- `--reload, -r` - Enable auto-reload

### Logs

```bash
pollingapi logs:view                # View log files
pollingapi logs:list                # List available logs
```

Options:
- `--file, -f` - Log file (zweitstimme, scraper, errors)
- `--lines, -n` - Number of lines (default: 50)
- `--follow, -F` - Follow log output

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Required variables:
- `API_SECRET` - Secret key for API authentication (change in production)

## API Endpoints

See `GET /docs` for complete API documentation. Main endpoints:
- `GET /` - API info
- `GET /health` - Health check
- `GET /polls/` - Polls data
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
