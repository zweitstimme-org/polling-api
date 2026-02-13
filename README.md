# Zweitstimme

German election polling data collection, cleaning, and API service.

## Overview

Zweitstimme is a unified Python application for collecting, cleaning, and serving German election polling data. It scrapes polling data from various sources (Wahlrecht.de, DAWUM API) and provides a cleaned, normalized dataset via REST API.

## Architecture

```
zweitstimme/
├── json/                      # Reference data (primary keys for relations)
│   ├── institutes.json        # Polling institute IDs
│   ├── methods.json           # Survey method IDs
│   ├── parliaments.json       # Parliament/election IDs
│   ├── parties.json           # Political party IDs
│   └── taskers.json           # Tasker/commissioner IDs
├── src/pollingapi/
│   ├── main.py                # FastAPI application
│   ├── cli.py                 # CLI entry points (zweitstimme command)
│   ├── database.py            # SQLite database configuration
│   ├── database_seed.py       # JSON-based database seeding
│   ├── models.py              # SQLAlchemy ORM models
│   ├── schemas.py             # Pydantic schemas
│   ├── api/                   # API routers
│   │   ├── polls.py
│   │   ├── download.py
│   │   ├── dictionaries.py
│   │   ├── elections.py
│   │   └── webhooks.py
│   ├── scraper/               # Web scraping module
│   │   ├── base.py            # Base scraper class
│   │   ├── runner.py          # Scraper orchestration
│   │   ├── wahlrecht.py       # Wahlrecht.de scrapers
│   │   ├── dawum.py           # DAWUM API scraper
│   │   └── workers/           # Scraper worker configs
│   │       ├── sites_bund/    # Federal election scrapers
│   │       └── sites_land/    # State election scrapers
│   └── cleaner/               # Data cleaning ETL pipeline
│       ├── pipeline.py
│       └── mappings/          # Data normalization mappings
├── data/                      # SQLite database and exports
│   └── polling.db             # Main database file
├── pyproject.toml
└── README.md
```

## Quick Start

### Installation

```bash
# Clone and navigate to project
cd zweitstimme

# Install with UV (recommended)
uv sync

# Or install with pip
pip install -e .
```

### Initialize Database

```bash
# Initialize database tables
zweitstimme db:init

# Seed reference tables from JSON files (institutes, parties, methods, etc.)
zweitstimme db:seed

# Verify database setup
zweitstimme db:tables
```

### Run API Server

```bash
# Start the API server
zweitstimme server:start

# With custom host/port
zweitstimme server:start --host 0.0.0.0 --port 8080

# With auto-reload (development)
zweitstimme server:start --reload
```

The API will be available at `http://localhost:8000`

## CLI Commands

Zweitstimme uses a colon-separated command structure for organization:

### Database Commands (`db:*`)

```bash
# Initialize database tables
zweitstimme db:init

# Reset database (destructive - drops all tables)
zweitstimme db:reset --confirm

# Seed reference tables from JSON files
zweitstimme db:seed

# Seed from Python mappings (legacy)
zweitstimme db:seed --mapping

# List database tables with row counts
zweitstimme db:tables

# Verify database connectivity
zweitstimme db:ping

# Export data to JSON files
zweitstimme db:export
```

### Scraper Commands (`scraper:*`)

```bash
# List all available scraper workers
zweitstimme scraper:list

# Run all scrapers
zweitstimme scraper:run all

# Run specific scraper
zweitstimme scraper:run forsa
zweitstimme scraper:run bayern
zweitstimme scraper:run dawum

# Dry run (don't insert to database)
zweitstimme scraper:run all --dry-run

# Debug mode (verbose logging)
zweitstimme scraper:run all --debug

# Check scraper status
zweitstimme scraper:status
```

### Pipeline Commands (`pipeline:*`)

```bash
# Run full pipeline (scraper + cleaner)
zweitstimme pipeline:run

# Run only scraper
zweitstimme pipeline:run --skip-clean

# Run only cleaner
zweitstimme pipeline:clean

# Inspect a specific raw poll
zweitstimme pipeline:inspect 123
```

## JSON Reference Data

The `json/` directory contains reference data with primary keys that are used throughout the system:

- **`institutes.json`** - Polling institutes (Forsa, INSA, etc.) with their IDs
- **`methods.json`** - Survey methods (Telefonisch, Online, etc.) with their IDs
- **`parliaments.json`** - Parliaments/elections (Bundestag, Bayern, etc.) mapped to elections table
- **`parties.json`** - Political parties (CDU/CSU, SPD, AfD, etc.) with their IDs
- **`taskers.json`** - Taskers/commissioners (BILD, RTL/n-tv, etc.) with their IDs

These JSON files define the exact primary keys used in the database relations. When seeding with `zweitstimme db:seed`, these IDs are preserved exactly as defined in the JSON.

Example from `parties.json`:
```json
{
  "1": {
    "Shortcut": "CDU/CSU",
    "Name": "Christlich Demokratische Union / Christlich-Soziale Union"
  },
  "2": {
    "Shortcut": "SPD",
    "Name": "Sozialdemokratische Partei Deutschlands"
  }
}
```

## Data Cleaning Pipeline

The cleaning pipeline (`zweitstimme pipeline:clean`) transforms raw scraped data into clean, normalized data:

### Philosophy

- **Never modifies** `polls_raw` table - raw data is preserved
- Uses **JSON-based mappings** to normalize names to canonical IDs
- Inserts cleaned data into `polls` and `poll_results` tables
- Prevents duplicates by checking existing cleaned polls

### JSON Mappings in Cleaning

The cleaner uses the JSON files to map scraper output to canonical IDs:

**Institute Mapping:**
- Scraper outputs: `"forsa"`, `"INSA"`, `"Allensbach"`
- JSON maps these to IDs: `2`, `5`, `9`
- Result: Clean poll has `institute_id = 2` (Forsa)

**Party Mapping:**
- Scraper outputs: `"AfD"`, `"SPD"`, `"GRÜNE"`
- JSON maps these to IDs: `7`, `2`, `4`
- Result: Clean poll results reference party IDs correctly

**Method Mapping:**
- Scraper outputs: `"Telefonisch"`, `"Online"`, `"Persönlich"`
- JSON maps these to IDs: `1`, `3`, `2`
- Result: Clean poll has correct `method_id`

**Election/Parliament Mapping:**
- Scraper outputs scope: `"bayern"`, `"berlin"`, `"federal"`
- JSON maps these to parliament IDs: `2`, `3`, `0`
- Result: Clean poll has correct `election_id`

### Example Transformation

Raw data in `polls_raw`:
```json
{
  "institute_id": "forsa",
  "parties": "{\"AfD\": 24.0, \"SPD\": 14.0}",
  "scope": "federal",
  "respondents": "2.503"
}
```

Cleaned data in `polls`:
```json
{
  "institute_id": 2,
  "scope": "federal",
  "respondents": 2503
}
```

Cleaned data in `poll_results`:
```json
[
  {"party_id": 7, "percentage": 24.0},
  {"party_id": 2, "percentage": 14.0}
]
```

## Scrapers

### Federal Election Scrapers (Bund)

- **allensbach** - Allensbach Institute
- **forsa** - Forsa polling data
- **infratest** - Infratest dimap
- **insa** - INSA polling data
- **verian** - Verian (formerly Emnid)
- **gms** - GMS polling
- **yougov** - YouGov polling

### State Election Scrapers (Land)

- **bayern** - Bavaria state polls
- **berlin** - Berlin state polls
- **brandenburg** - Brandenburg state polls
- **bremen** - Bremen state polls
- **hamburg** - Hamburg state polls
- **hessen** - Hesse state polls
- **mecklenburg-vorpommern** - Mecklenburg-Vorpommern polls
- **niedersachsen** - Lower Saxony polls
- **nrw** - North Rhine-Westphalia polls
- **rheinland-pfalz** - Rhineland-Palatinate polls
- **saarland** - Saarland polls
- **sachsen** - Saxony polls
- **sachsenanhalt** - Saxony-Anhalt polls
- **schleswig-holstein** - Schleswig-Holstein polls
- **thüringen** - Thuringia polls

### API Scrapers

- **dawum** - DAWUM API (comprehensive polling data)

## URL Handling Strategy

Scrapers automatically handle historic vs current URLs:

- **Historic URLs** (containing year like `2002.htm`, `2017.htm`) - Processed once and marked as complete
- **Current URLs** (no year in filename) - Processed on every run to get fresh data

This prevents re-processing old data while ensuring current data is always up-to-date.

## Logging System

Zweitstimme uses a centralized logging system with multiple outputs:

### Log Files

All logs are stored in `data/logs/`:

- **`zweitstimme.log`** - Main application log (all log levels)
- **`scraper.log`** - Scraper-specific detailed logs
- **`errors.log`** - Error-level logs only

### Log Format

Logs include:
- Timestamp
- Logger name (module)
- Log level (DEBUG, INFO, WARNING, ERROR)
- Source file and line number
- Message

Example:
```
2026-02-10 20:00:15,275 - forsa - INFO - [base.py:280] - Processing 1 URLs for forsa
```

### Debug Mode

Enable debug logging for verbose output:

```bash
# Run scraper with debug logging
zweitstimme scraper:run forsa --debug

# This sets log level to DEBUG and shows detailed information
```

### Log Rotation

Log files automatically rotate when they reach 10 MB, keeping up to 5 backup files. This prevents disk space issues during long-running operations.

## API Endpoints

### Information
- `GET /` - API information
- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation

### Polls
- `GET /polls/` - Get all cleaned polls
- `GET /polls/results` - Get all poll results
- `GET /polls/range?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Filter by date
- `GET /polls/election/{election_id}` - Filter by election

### Raw Polls
- `GET /raw/` - Get all raw polls
- `GET /raw/latest` - Get 100 most recent raw polls
- `GET /raw/stream` - Stream all raw polls

### Downloads
- `GET /download/json` - Download polls as JSON
- `GET /download/sqlite` - Download SQLite database
- `GET /download/csv` - Download as CSV

### Dictionaries
- `GET /dict/methods` - List survey methods
- `GET /dict/parties` - List political parties
- `GET /dict/providers` - List data providers
- `GET /dict/institutes` - List polling institutes
- `GET /dict/elections` - List elections

### Webhooks (requires API secret)
- `POST /webhooks/scrape` - Trigger scraper
- `POST /webhooks/clean` - Trigger cleaner
- `POST /webhooks/pipeline` - Trigger full pipeline

## Configuration

Create a `.env` file:

```env
# API Configuration
API_TITLE=Zweitstimme API
API_VERSION=1.0.0
API_HOST=0.0.0.0
API_PORT=8000

# Security
API_SECRET=your-secret-key

# Database (default: data/polling.db)
DATABASE_URL=sqlite:///data/polling.db

# GitHub (for data sync)
GITHUB_TOKEN=your-github-token
GITHUB_REPO=your-org/data
```

## Database Schema

### Reference Tables (Populated from JSON)
- **institutes** - Polling institutes (22 records)
- **methods** - Survey methods (5 records)
- **parties** - Political parties (26 records)
- **taskers** - Taskers/commissioners (111 records)
- **elections** - Elections (18 records)

### Data Tables
- **polls_raw** - Raw scraped poll data
- **polls** - Cleaned, normalized poll data
- **poll_results** - Individual party results per poll

## Development

### Run with Auto-reload

```bash
zweitstimme server:start --reload
```

### Database Management

```bash
# Check database connection
zweitstimme db:ping

# View table counts
zweitstimme db:tables

# Export data
zweitstimme db:export
```

### Testing Scrapers

```bash
# Test a scraper in dry-run mode
zweitstimme scraper:run forsa --dry-run

# Run with debug output
zweitstimme scraper:run bayern --debug
```

## Project Structure

- **API**: FastAPI application serving polling data
- **Scraper**: Web scraping module for collecting raw data from Wahlrecht.de and DAWUM API
- **Cleaner**: ETL pipeline for normalizing and cleaning data
- **Database**: SQLite with SQLAlchemy ORM, populated from JSON reference files

## License

MIT License
