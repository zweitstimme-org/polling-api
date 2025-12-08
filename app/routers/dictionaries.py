from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Election, Method, Party, Provider, Tasker
from ..schemas import (
    Election as ElectionSchema,
    Method as MethodSchema,
    Party as PartySchema,
    Provider as ProviderSchema,
    Tasker as TaskerSchema,
)

router = APIRouter(prefix="/dict", tags=["dict"])


@router.get("/methods", response_model=List[MethodSchema])
def get_methods(db: Session = Depends(get_db)):
    """Get all polling methods."""
    methods = db.query(Method).all()
    return methods


@router.get("/parties", response_model=List[PartySchema])
def get_parties(db: Session = Depends(get_db)):
    """Get all parties."""
    parties = db.query(Party).all()
    return parties


@router.get("/providers", response_model=List[ProviderSchema])
def get_providers(db: Session = Depends(get_db)):
    """Get all providers."""
    providers = db.query(Provider).all()
    return providers


@router.get("/taskers", response_model=List[TaskerSchema])
def get_taskers(db: Session = Depends(get_db)):
    """Get all taskers."""
    taskers = db.query(Tasker).all()
    return taskers


@router.get("/elections", response_model=List[ElectionSchema])
def get_elections(db: Session = Depends(get_db)):
    """Get all elections."""
    elections = db.query(Election).all()
    return elections
