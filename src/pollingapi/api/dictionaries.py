"""Reference/dictionary API routes."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pollingapi.database import get_db
from pollingapi.models import Election, Institute, Method, Party, Provider, Tasker
from pollingapi.schemas import (
    Election as ElectionSchema,
)
from pollingapi.schemas import (
    Institute as InstituteSchema,
)
from pollingapi.schemas import (
    Method as MethodSchema,
)
from pollingapi.schemas import (
    Party as PartySchema,
)
from pollingapi.schemas import (
    Provider as ProviderSchema,
)

router = APIRouter(prefix="/reference", tags=["reference"])


class AllReferenceResponse(BaseModel):
    institutes: list[InstituteSchema]
    parties: list[PartySchema]
    providers: list[ProviderSchema]
    methods: list[MethodSchema]
    elections: list[ElectionSchema]
    taskers: list[dict[str, Any]]


@router.get("/institutes", response_model=list[InstituteSchema])
def list_institutes(db: Session = Depends(get_db)):
    """List all institutes."""
    return db.query(Institute).order_by(Institute.key.asc()).all()


@router.get("/parties", response_model=list[PartySchema])
def list_parties(db: Session = Depends(get_db)):
    """List all parties."""
    return db.query(Party).order_by(Party.key.asc()).all()


@router.get("/providers", response_model=list[ProviderSchema])
def list_providers(db: Session = Depends(get_db)):
    """List all providers."""
    return db.query(Provider).order_by(Provider.id.asc()).all()


@router.get("/methods", response_model=list[MethodSchema])
def list_methods(db: Session = Depends(get_db)):
    """List all methods."""
    return db.query(Method).order_by(Method.key.asc()).all()


@router.get("/elections", response_model=list[ElectionSchema])
def list_elections(db: Session = Depends(get_db)):
    """List all elections."""
    return db.query(Election).order_by(Election.key.asc()).all()


@router.get("/taskers", response_model=list[dict[str, Any]])
def list_taskers(db: Session = Depends(get_db)):
    """List all taskers."""
    rows = db.query(Tasker).order_by(Tasker.id.asc()).all()
    return [{"id": row.id, "name": row.name, "description": row.description} for row in rows]


@router.get("/all", response_model=AllReferenceResponse)
def list_all_reference(db: Session = Depends(get_db)):
    """Get all reference tables in one response."""
    institutes = db.query(Institute).order_by(Institute.key.asc()).all()
    parties = db.query(Party).order_by(Party.key.asc()).all()
    providers = db.query(Provider).order_by(Provider.id.asc()).all()
    methods = db.query(Method).order_by(Method.key.asc()).all()
    elections = db.query(Election).order_by(Election.key.asc()).all()
    taskers_rows = db.query(Tasker).order_by(Tasker.id.asc()).all()
    taskers = [
        {"id": row.id, "name": row.name, "description": row.description} for row in taskers_rows
    ]
    return {
        "institutes": institutes,
        "parties": parties,
        "providers": providers,
        "methods": methods,
        "elections": elections,
        "taskers": taskers,
    }
