# app/routers/database_insert.py
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models import RawPolls
from app.schemas import IngestResult, RawPollBatchIn, RawPollIn

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _prepare_payload(poll: RawPollIn) -> Dict[str, Any]:
    data = poll.model_dump(by_alias=True, exclude_none=True)
    parties = data.get("parties")
    if parties is not None and not isinstance(parties, str):
        data["parties"] = json.dumps(parties, ensure_ascii=False)
    return data


@router.post("/polls", response_model=IngestResult)
async def ingest_polls(body: RawPollBatchIn, db: AsyncSession = Depends(get_async_db)):
    if not body.polls:
        return IngestResult(inserted=0, record_ids=[])

    inserted_ids: List[int] = []

    for poll in body.polls:
        payload = _prepare_payload(poll)
        stmt = insert(RawPolls).values(**payload).returning(RawPolls.id)
        try:
            result = await db.execute(stmt)
        except SQLAlchemyError as exc:  # pragma: no cover - bubble up as HTTP error
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        inserted_id = result.scalar_one()
        inserted_ids.append(inserted_id)

    await db.commit()
    return IngestResult(inserted=len(inserted_ids), record_ids=inserted_ids)
