from fastapi import APIRouter, Header, HTTPException, Request

from app.utils.election_date import scrape_dates
from app.utils.notifier import notify_background

router = APIRouter()
SECRET = "supersecret"


# TODO: remove from schema
@router.post("/webhook/dates", include_in_schema=True)
async def webhook_dates(request: Request, x_secret: str = Header(...)):
    if x_secret != SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_host = request.client.host if request.client else "unknown"
    headers = dict(request.headers)

    try:
        results = await scrape_dates()
        msg = (
            f"Webhook /dates triggered\n"
            f"Client: {client_host}\n"
            f"Headers: {headers}\n\n"
            f"Result: success, rows={len(results)}"
        )
        notify_background("Election Dates Scraper", msg)
        return {"status": "success", "rows": len(results)}
    except Exception as e:
        msg = (
            f"Webhook /dates triggered\n"
            f"Client: {client_host}\n"
            f"Headers: {headers}\n\n"
            f"Result: failed, error={str(e)}"
        )
        notify_background("Election Dates Scraper FAILED", msg)
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")
