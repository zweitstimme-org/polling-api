from pathlib import Path

DATA_PATH = Path("./data")
DATA_PATH.mkdir(exist_ok=True)

NEW_DB = DATA_PATH / "polls.db"

# TODO: Implement the proper pull_db function


async def pull_db():
    return
