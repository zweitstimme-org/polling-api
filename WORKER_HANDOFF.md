# Polling API Worker Handoff Guide

This handoff tells new workers exactly how to move raw polling data into the service. The worker’s only job is to package validated polls and send them to the FastAPI ingestion endpoint. Never connect to Postgres directly and never write to any table yourself—the API performs every database write on your behalf.

## Worker Contract
- **Do** normalize raw polls into the request format described below and POST them to `POST /ingest/polls`.
- **Do** handle HTTP errors, retry when appropriate, and log any payloads the API rejects.
- **Do** keep payload fields aligned with the `polls_raw` schema so the downstream cleaner can promote them.
- **Don’t** open manual SQL connections, touch normalized tables, or assume the database schema outside of this contract.
- **Don’t** hard-code hosts; read the API base URL from configuration so you can target local or deployed environments.

## Runtime & Project Layout (Context Only)
- **FastAPI service**: `app/main.py` wires routers for ingestion, exports, webhooks, and metadata. CORS stays permissive for now.
- **Database bootstrap**: `app/db_init.py` creates the Postgres schema (`Base.metadata.create_all()`). FastAPI runs `init_db()` at startup; `scripts/init_db.py` mirrors that logic for manual bootstraps.
- **Database config**: `app/database.py` exposes sync/async SQLAlchemy engines from `DATABASE_URL` / `ASYNC_DATABASE_URL`. Defaults point at `postgresql+psycopg://postgres:postgres@localhost:5432/pollingapi_dev`.
- **Schemas**: ORM models live in `app/models.py`; Pydantic request/response models in `app/schemas.py`.
- **Router of interest**: `app/routers/database_insert.py` hosts the ingestion endpoint that the worker calls. Treat it as the single integration point.

## Raw Poll Payload Specification
Everything you send maps 1:1 into the `polls_raw` table once the API validates it.

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `source` | ✅ | `string` | Unique provider identifier used for dedupe; keep consistent across runs. |
| `publish_date` | ✅ | `string` | ISO-like date (e.g., `2024-04-25`). Stored verbatim. |
| `survey_date_start` | ✅ | `string` | Beginning of the fieldwork period. |
| `survey_date_end` | ✅ | `string` | End of the fieldwork period. |
| `parties` | ✅ | `object` or `string` | Party → percentage map. If object, API JSON-serializes it before insertion. |
| `date_downloaded` | ✅ | `string` | Timestamp when you scraped the poll (ISO recommended). |
| `Befragte` | ❌ | `string` | Sample size; send raw value if known. |
| `Zeitraum` | ❌ | `string` | Original survey range label. |
| `institute_id` | ❌ | `string` | Lookup key for polling institute. |
| `forecast_provider` | ❌ | `string` | Lookup key for forecasting vendor. |
| `scope` | ❌ | `string` | Example: `national`, `state`, etc. |
| `election_id` | ❌ | `string` | Maps to elections table downstream. |
| `method_id` | ❌ | `string` | Sampling method reference. |

> The API stores every field as received. Downstream ETL jobs promote rows into normalized tables (`polls`, `poll_results`, lookups) but the worker never writes to them directly.

## FastAPI Ingestion Flow
- **Endpoint**: `POST {API_BASE_URL}/ingest/polls`
- **Headers**: `Content-Type: application/json`. Authentication is currently not required.
- **Request body**: JSON object with a `polls` array containing one or more entries matching the table above. All polls in a batch must use the same schema revision.
- **Validation**: Missing required fields, invalid JSON, or unsupported types produce `422` responses. Duplicate `source` + date combinations currently insert as-is; dedupe is handled later.
- **Response**: On success, the API returns `{ "inserted": <int>, "record_ids": [<int>, ...] }`.
- **Error handling**:
  - `4xx`: Treat as permanent unless the response JSON clearly indicates a transient validation error you can fix quickly.
  - `5xx` or timeouts: retry with backoff; keep retries idempotent by resending the same payload.

### Canonical Example
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

Variants you can rely on:
- `parties` may be sent as a JSON string (`"{\"CDU\": 29.0}"`).
- Optional fields can be omitted entirely; the API stores `NULL` in those columns.

## Local FastAPI Target
Development assumes the API runs locally via `dev.compose.yaml`, exposing `http://localhost:8000`.

- Export `API_BASE_URL=http://localhost:8000` (or inject it through your worker’s config file/environment).
- Smoke test connectivity before running a full scrape:
  ```bash
  curl -X POST "${API_BASE_URL}/ingest/polls" \
       -H 'Content-Type: application/json' \
       -d '{"polls": []}'
  ```
  A `200` with `{"inserted":0,"record_ids":[]}` confirms the route is live.
- When running the worker inside Docker, attach it to the same compose network and set `API_BASE_URL=http://api:8000` if `api` is the service name. No database credentials are needed by the worker container.

## Operational Checklist
- **Before sending**: Validate schemas, ensure timestamps are ISO-8601, and keep `source` identifiers consistent. Log outgoing payloads for auditing.
- **During execution**: Batch inserts when possible (e.g., 50–100 polls per request) to reduce chatter. Respect API rate limits your deployment might impose.
- **On failure**: Record the response payload, implement exponential backoff for retries, and escalate consistent validation errors with a sample payload.
- **Monitoring**: Track polls processed, successful inserts, and failure counts. Capture the most recent `record_ids` so you can reconcile against the API if needed.

Stay within this contract and the FastAPI service will manage all persistence, schema evolution, and downstream normalization for you.
