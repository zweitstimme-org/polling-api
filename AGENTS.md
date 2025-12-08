# Repository Guidelines

## Project Structure & Module Organization
- `app/` holds the FastAPI application: `main.py` wires routers, `routers/` contains feature slices (poll ingestion, downloads, hooks), `database.py` configures sync/async SQLAlchemy engines, and `models.py` defines ORM tables.
- `scripts/` provides operational CLIs such as `init_db.py`; invoke them with `uv run python scripts/init_db.py` so imports resolve.
- `data/` stores JSON/CSV/SQLite/Parquet artifacts that the `/polls/export/*` endpoints stream. Keep generated files small and overwrite in place to avoid bloating the repo history.
- `compose.yaml` targets production-like runs, while `dev.compose.yaml` mounts the working tree for rapid iteration.

## Build, Test, and Development Commands
- `uv sync` – install dependencies (Python 3.13 runtime expected).
- `docker compose up db` – start the Postgres service defined in `compose.yaml`.
- `uv run python scripts/init_db.py` – create the `pollingapi_dev` schema locally.
- `uv run fastapi dev app/main.py` – launch the API with autoreload on http://localhost:8000.
- `docker compose -f dev.compose.yaml up --build` – run the full stack in containers; ideal for smoke tests that mimic deployment.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, descriptive snake_case for functions/variables, and PascalCase for SQLAlchemy models.
- Prefer type hints and `pydantic` models for all request/response contracts; match schema attribute names to column names when possible.
- Keep module-level configuration (env lookups, constants) near the top of each file and document non-obvious logic with short comments.

## Testing Guidelines
- Automated tests are not yet present; when contributing, add `tests/` mirroring the router or utility structure.
- Use `pytest` naming (`test_<module>.py`, `test_<feature>`) and target async routes with `pytest-asyncio` fixtures.
- Run `uv run pytest` locally plus `uv run pyright` for static checks before opening a PR.

## Commit & Pull Request Guidelines
- Recent history (`git log`) shows concise, lower-case summaries (e.g., "added new build", "updated favicon"); follow the same pattern but prefer imperative verbs: "add dev compose stack".
- Each pull request should reference the relevant issue, describe the change, list testing evidence (commands + results), and include screenshots for UI/asset updates when applicable.

## Security & Configuration Tips
- Populate `.env` with `DATABASE_URL`, `ASYNC_DATABASE_URL`, and optional metadata overrides before running any command; never commit the file.
- Least-privilege practice: when sharing compose files, omit secrets and rely on Docker secrets or CI-provided env vars for production credentials.
