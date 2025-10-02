from fastapi import APIRouter, Header, HTTPException, Request

from app.utils.bundestag_scraper import scrape_and_save
from app.utils.notifier import notify_background

router = APIRouter()
SECRET = "supersecret"


# TODO: remove from schema
@router.post("/webhook/scrape", include_in_schema=True)
async def webhook_scrape(request: Request, x_secret: str = Header(...)):
    if x_secret != SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_host = request.client.host if request.client else "unknown"
    headers = dict(request.headers)

    try:
        results = await scrape_and_save()
        msg = (
            f"Webhook /scrape triggered\n"
            f"Client: {client_host}\n"
            f"Headers: {headers}\n\n"
            f"Result: success, rows={len(results)}"
        )
        notify_background("Bundestag Scraper", msg)
        return {"status": "success", "rows": len(results)}
    except Exception as e:
        msg = (
            f"Webhook /scrape triggered\n"
            f"Client: {client_host}\n"
            f"Headers: {headers}\n\n"
            f"Result: failed, error={str(e)}"
        )
        notify_background("Bundestag Scraper FAILED", msg)
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")
