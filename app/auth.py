from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests as rq

security = HTTPBearer()
API_TOKEN = "supersecrettoken123"  # Replace with your real secret


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")
    rq.post(
        "https://ntfy.sh/zweitstimme_org",
        data="Post Request has been Made to DB",
        headers={"Tags": "warning"},
    )
    return True
