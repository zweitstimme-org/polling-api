# Justfile for pollingAPI
# Documentation: https://just.systems

# =============================================================================
# DEVELOPMENT COMMANDS
# =============================================================================

# Initialize database and seed reference tables
[group('dev: database')]
init:
    @echo "Initializing database..."
    uv run pollingapi db:init
    @echo "Seeding database..."
    uv run pollingapi db:seed

# Full dev setup: init + run all scrapers + clean
[group('dev: setup')]
dev-init:
    @echo "=== Initializing database ==="
    uv run pollingapi db:init
    uv run pollingapi db:seed
    @echo "=== Running scrapers ==="
    uv run pollingapi scraper:run forsa
    uv run pollingapi scraper:run dawum
    uv run pollingapi scraper:run insa
    uv run pollingapi pipeline:clean
    @echo "=== Dev setup complete ==="

# Run all scrapers and clean
[group('dev: scrapers')]
dev:
    @echo "=== Running scrapers ==="
    uv run pollingapi scraper:run forsa
    uv run pollingapi scraper:run dawum
    uv run pollingapi scraper:run insa
    uv run pollingapi pipeline:clean
    @echo "=== Scrapers complete ==="

# Run a specific scraper
[group('dev: scrapers')]
run SCRAPER:
    uv run pollingapi scraper:run {{ SCRAPER }}

# List available scrapers
[group('dev: scrapers')]
scraper-list:
    uv run pollingapi scraper:list

# Check scraper status
[group('dev: scrapers')]
scraper-status:
    uv run pollingapi scraper:status

# Run the cleaning pipeline
[group('dev: pipeline')]
clean:
    uv run pollingapi pipeline:clean

# Inspect pipeline data
[group('dev: pipeline')]
inspect:
    uv run pollingapi pipeline:inspect

# Export all data
[group('dev: export')]
export-data:
    uv run pollingapi export:all

# View logs
[group('dev: logs')]
logs:
    uv run pollingapi logs:view

# List log files
[group('dev: logs')]
logs-list:
    uv run pollingapi logs:list

# Reset database (requires confirmation)
[confirm("This will delete all data and recreate the database. Continue?")]
[group('dev: database')]
db-reset:
    @echo "Resetting database..."
    uv run pollingapi db:reset
    @echo "Database reset complete!"

# Delete database file (requires confirmation)
[confirm("Delete the database file? This cannot be undone!")]
[group('dev: database')]
kill:
    rm -f data/polling.db
    @echo "Database deleted!"

# =============================================================================
# PRODUCTION COMMANDS
# =============================================================================

# Start API server (development mode)
[group('prod: server')]
serve:
    uv run pollingapi server:start -p 8080

# Start API server (production mode with gunicorn/uvicorn workers)
[group('prod: server')]
serve-prod:
    uv run pollingapi server:prod

# Run ETL pipeline
[group('prod: pipeline')]
pipeline-run:
    uv run pollingapi pipeline:run

# Build/update the database, import archive data, run collection, clean, validate, export, archive
[group('prod: pipeline')]
deploy:
    @echo "=== Syncing environment ==="
    uv sync
    @echo "=== Initializing database ==="
    uv run pollingapi db:init
    uv run pollingapi db:seed
    @echo "=== Validating public policy ==="
    uv run pollingapi policy:validate
    @echo "=== Downloading import data ==="
    uv run pollingapi import:download
    @echo "=== Importing Kayser/Rehmert data ==="
    uv run pollingapi import:run KAYSER_REHMERT.xlsx --source kayser_rehmert
    @echo "=== Running scraper, cleaner, validation, export, and archive ==="
    uv run pollingapi pipeline:run

# Database ping (health check)
[group('prod: health')]
ping:
    uv run pollingapi db:ping

# =============================================================================
# QUALITY ASSURANCE
# =============================================================================

# Run linter
[group('qa: lint')]
lint:
    uv run ruff check src/

# Format code
[group('qa: format')]
format:
    uv run ruff format src/

# Type check
[group('qa: typecheck')]
typecheck:
    uv run mypy src/

# Run all tests
[group('qa: test')]
test:
    uv run pytest tests/

# Run tests with coverage
[group('qa: test')]
test-cov:
    uv run pytest tests/ --cov=src/pollingapi --cov-report=term-missing

# Run specific test file
[group('qa: test')]
test-file FILE:
    uv run pytest tests/{{ FILE }}

# =============================================================================
# UTILITIES
# =============================================================================

# Show all available commands (default when running just)
[default]
[group('util')]
help:
    @just --list --unsorted
