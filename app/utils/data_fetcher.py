# app/utils/data_fetcher.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # loads GITHUB_TOKEN and GITHUB_REPO from .env

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO   = os.getenv("GITHUB_REPO")  
DATA_DIR      = "./data"

def fetch_data():
    """Fetch the latest data files from a private GitHub repo release."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"status": "error", "message": "Missing GITHUB_TOKEN or GITHUB_REPO env vars"}

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # Get latest release metadata
        resp = requests.get(GITHUB_REPO, headers=headers)
        resp.raise_for_status()
        release = resp.json()
        assets = release.get("assets", [])

        # 2) Download each asset
        for asset in assets:
            asset_api_url = asset["url"]           # API endpoint for the asset
            file_name     = asset["name"]

            dl_headers = {
                **headers,
                "Accept": "application/octet-stream"
            }
            dl_resp = requests.get(asset_api_url, headers=dl_headers)
            dl_resp.raise_for_status()

            # ensure data dir exists
            os.makedirs(DATA_DIR, exist_ok=True)
            file_path = os.path.join(DATA_DIR, file_name)
            with open(file_path, "wb") as f:
                f.write(dl_resp.content)

        return {"status": "success", "message": "Data files downloaded successfully."}

    except requests.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
