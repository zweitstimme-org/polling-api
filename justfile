# Justfile for Zweitstimme development workflow

# Initialize database and seed reference tables
init:
    @echo "Initializing database..."
    uv run zweitstimme db:init
    @echo "Seeding database..."
    uv run zweitstimme db:seed

# Init and Run development scrapers (forsa, dawum, insa)
dev-init:
    @echo "Initializing database..."
    uv run zweitstimme db:init
    @echo "Seeding database..."
    uv run zweitstimme db:seed
    @echo "Running forsa scraper..."
    uv run zweitstimme scraper:run forsa
    @echo "Running dawum scraper..."
    uv run zweitstimme scraper:run dawum
    @echo "Running insa scraper..."
    uv run zweitstimme scraper:run insa
    @echo "Cleaning Polls"
    uv run zweitstimme pipeline:clean
    @echo "Dev scrapers complete!"

# Run development scrapers (forsa, dawum, insa)
dev:
    @echo "Running forsa scraper..."
    uv run zweitstimme scraper:run forsa
    @echo "Running dawum scraper..."
    uv run zweitstimme scraper:run dawum
    @echo "Running insa scraper..."
    uv run zweitstimme scraper:run insa
    @echo "Cleaning Polls"
    uv run zweitstimme pipeline:clean
    @echo "Dev scrapers complete!"

# Run a single scraper
run SCRAPER:
    uv run zweitstimme scraper:run {{ SCRAPER }}

# Run the cleaning pipeline
clean:
    uv run zweitstimme pipeline:clean

# Export all data
export:
    uv run zweitstimme export:all

# Start the API server
serve:
    uv run zweitstimme server:start -p 8080

# Show all available commands
help:
    @just --list

# Delete the database file (requires confirmation)
[confirm("Delete the database file? This cannot be undone! (y/n)")]
kill:
    rm -f data/polling.db
    @echo "Database deleted!"
