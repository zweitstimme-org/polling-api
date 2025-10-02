from pathlib import Path

import httpx
import pandas as pd

DATA_PATH = Path("./data")
DATA_PATH.mkdir(exist_ok=True)

RESULTS_FILE = DATA_PATH / "bundestagswahl.json"


async def scrape_and_save():
    url = "https://www.bundestag.de/parlament/wahlen/ergebnisse_seit1949-244692"

    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        r.raise_for_status()
        html = r.text

    # Pandas can extract all tables — we expect the first one
    dfs = pd.read_html(html)
    df = dfs[0]

    # Add the election column
    df["election"] = "bundestagswahl"

    # Convert to list of dicts
    results = df.to_dict(orient="records")

    # Save JSON
    df.to_json(RESULTS_FILE, orient="records", force_ascii=False, indent=2)

    return results
