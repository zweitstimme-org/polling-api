import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/polls", tags=["export"])


@router.get("/export/json")
def export_json():
    """export polls in JSON format"""
    json_path = "./data/polls.json"

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="JSON file not found")

    return FileResponse(
        path=json_path,
        filename="german_election_polls.json",
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=german_election_polls.json"
        },
    )


@router.get("/export/sqlite")
def export_sqlite():
    """export polls in SQLite format"""
    db_path = "./data/polls.db"

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    return FileResponse(
        path=db_path,
        filename="german_election_polls.db",
        media_type="application/x-sqlite3",
        headers={
            "Content-Disposition": "attachment; filename=german_election_polls.db"
        },
    )


# TODO: Change to proper export
# @router.get("/export/sql")
# def export_sql():
#    """export polls in SQL format"""
#    db_path = "./data/polls.db"
#
#    if not os.path.exists(db_path):
#        raise HTTPException(status_code=404, detail="Database file not found")
#
#    # Create SQL dump
#    conn = sqlite3.connect(db_path)
#    sql_dump = ""
#
#    # Add schema
#    for line in conn.iterdump():
#        sql_dump += line + "\n"
#
#    conn.close()
#
#    return Response(
#        content=sql_dump,
#        media_type="application/sql",
#        headers={
#            "Content-Disposition": "attachment; filename=german_election_polls.sql"
#        }
#    )
#


@router.get("/export/csv")
def download_csv():
    """Download polls in CSV format"""
    csv_path = "./data/polls.csv"

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found")

    return FileResponse(
        path=csv_path,
        filename="german_election_polls.csv",
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=german_election_polls.csv"
        },
    )


@router.get("/export/parquet")
def download_parquet():
    """Download polls in Parquet format"""
    parquet_path = "./data/polls.parquet"

    if not os.path.exists(parquet_path):
        raise HTTPException(status_code=404, detail="Parquet file not found")

    return FileResponse(
        path=parquet_path,
        filename="german_election_polls.parquet",
        media_type="application/octet-stream",  # or "application/x-parquet"
        headers={
            "Content-Disposition": "attachment; filename=german_election_polls.parquet"
        },
    )


@router.get("/export/raw")
def export_raw_json():
    """Export raw polls in JSON format (unprocessed data)"""
    json_path = "./data/export/polls_raw.json"

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Raw JSON file not found")

    return FileResponse(
        path=json_path,
        filename="german_election_polls_raw.json",
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=german_election_polls_raw.json"
        },
    )
