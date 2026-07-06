"""Validation report API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pollingapi.data_validation import ValidationReportService
from pollingapi.database import get_db
from pollingapi.schemas import ValidationReport

router = APIRouter(prefix="/validation", tags=["validation"])
DBSession = Annotated[Session, Depends(get_db)]


@router.get("/report", response_model=ValidationReport)
def get_validation_report(
    db: DBSession,
    top: Annotated[int, Query(ge=1, le=20, description="Number of top failures")] = 5,
):
    """Return aggregate validation quality report."""
    return ValidationReportService(db).build_report(top_n=top)
