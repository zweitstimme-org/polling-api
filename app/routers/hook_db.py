from fastapi import APIRouter, Header, HTTPException, Request

from app.utils.notifier import notify_background
from app.utils.pull_db import pull_db

router = APIRouter()
SECRET = "supersecret"


@router.post("/webhook/hook_db", include_in_schema=True)
async def webhook_db(request: Request, x_secret: str = Header(...)):
    if x_secret != SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_host = request.client.host if request.client else "unknown"
    headers = dict(request.headers)

    try:
        results = await pull_db()
        msg = (
            f"Webhook /Pull db ...\n"
            f"Client: {client_host}\n"
            f"Headers: {headers}\n\n"
            f"Result: success, rows={len(results)}"
        )
        notify_background("Pull DB", msg)
        return {"status": "success", "rows": len(results)}
    except Exception as e:
        msg = (
            f"Webhook /Pull db\n"
            f"Client: {client_host}\n"
            f"Headers: {headers}\n\n"
            f"Result: failed, error={str(e)}"
        )
        notify_background("Pulling db FAILED", msg)
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")
