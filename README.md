# polling-api

Current test version available at 

https://api.fasttrack29.com/docs


## Local development

1. Install dependencies using `uv sync` (Python 3.13).
2. Start the Postgres instance: `docker compose up db`.
3. Create the database schema: `uv run python scripts/init_db.py`.
4. Run the API locally: `uv run fastapi dev app/main.py`.

The application expects a `DATABASE_URL` pointing to the Postgres instance. An example value is provided in `.env` and matches the credentials defined in `compose.yaml`.

### Ingesting raw polls

Send a `POST /ingest/polls` request with JSON shaped like:

```json
{
  "polls": [
    {
      "source": "bundestag",
      "publish_date": "2024-04-25",
      "survey_date_start": "2024-04-20",
      "survey_date_end": "2024-04-23",
      "parties": {"CDU": 29.0, "SPD": 17.5}
    }
  ]
}
```

Only `source` is required; other fields map directly to the columns in `polls_raw` and can be omitted when data is unavailable.
