"""SQLAlchemy models for polling data."""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime as DateTimeType
from typing import List

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pollingapi.database import Base


class RawPoll(Base):
    """Raw poll data from scrapers."""

    __tablename__ = "polls_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    publish_date: Mapped[str | None] = mapped_column(String(50))
    survey_date_start: Mapped[str | None] = mapped_column(String(50))
    survey_date_end: Mapped[str | None] = mapped_column(String(50))
    respondents: Mapped[str | None] = mapped_column(String(100))
    zeitraum: Mapped[str | None] = mapped_column("Zeitraum", String(100))
    parties: Mapped[str | None] = mapped_column(Text)
    institute_id: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(100))
    tasker: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(100))
    scope: Mapped[str | None] = mapped_column(String(100))
    election_id: Mapped[str | None] = mapped_column(String(100))
    method_id: Mapped[str | None] = mapped_column(String(100))
    date_downloaded: Mapped[str | None] = mapped_column(String(50))

    # Run traceability — links this row to the pipeline_runs record that ingested it.
    # No FK constraint yet; constraint migration is deferred.
    pipeline_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # Relationship to cleaned poll
    cleaned_poll: Mapped[Poll | None] = relationship("Poll", back_populates="raw_poll")


class Institute(Base):
    """Polling institute."""

    __tablename__ = "institutes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    # Relationships
    polls: Mapped[List[Poll]] = relationship("Poll", back_populates="institute")


class Party(Base):
    """Political party."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    short_name: Mapped[str | None] = mapped_column(String(20))
    color: Mapped[str | None] = mapped_column(String(7))  # Hex color

    # Relationships
    poll_results: Mapped[List[PollResult]] = relationship("PollResult", back_populates="party")


class Provider(Base):
    """Data provider."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    # Relationships
    polls: Mapped[List[Poll]] = relationship("Poll", back_populates="provider")


class Tasker(Base):
    """Tasker/commissioner."""

    __tablename__ = "taskers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)


class Election(Base):
    """Election type."""

    __tablename__ = "elections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    election_type: Mapped[str] = mapped_column(String(50), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    scope: Mapped[str | None] = mapped_column(String(50))
    date: Mapped[DateType | None] = mapped_column(Date, nullable=True)

    # Relationships
    polls: Mapped[List[Poll]] = relationship("Poll", back_populates="election")

    __table_args__ = (UniqueConstraint("election_type", "year", "scope", name="uix_election"),)


class Method(Base):
    """Survey method."""

    __tablename__ = "methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    # Relationships
    polls: Mapped[List[Poll]] = relationship("Poll", back_populates="method")


class Poll(Base):
    """Clean, normalized poll data."""

    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    raw_id: Mapped[int | None] = mapped_column(
        ForeignKey("polls_raw.id"), unique=True, nullable=True
    )
    publish_date: Mapped[DateType | None] = mapped_column(Date)
    survey_date_start: Mapped[DateType | None] = mapped_column(Date)
    survey_date_end: Mapped[DateType | None] = mapped_column(Date)
    respondents: Mapped[int | None] = mapped_column(Integer)
    institute_id: Mapped[int | None] = mapped_column(ForeignKey("institutes.id"))
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"))
    election_id: Mapped[int | None] = mapped_column(ForeignKey("elections.id"))
    method_id: Mapped[int | None] = mapped_column(ForeignKey("methods.id"))
    source: Mapped[str | None] = mapped_column(String(100))
    scope: Mapped[str | None] = mapped_column(String(100))
    date_downloaded: Mapped[DateTimeType | None] = mapped_column(DateTime)

    # Relationships
    raw_poll: Mapped[RawPoll | None] = relationship("RawPoll", back_populates="cleaned_poll")
    institute: Mapped[Institute | None] = relationship("Institute", back_populates="polls")
    provider: Mapped[Provider | None] = relationship("Provider", back_populates="polls")
    election: Mapped[Election | None] = relationship("Election", back_populates="polls")
    method: Mapped[Method | None] = relationship("Method", back_populates="polls")
    results: Mapped[List[PollResult]] = relationship(
        "PollResult", back_populates="poll", cascade="all, delete-orphan"
    )


class PollResult(Base):
    """Individual party result for a poll."""

    __tablename__ = "poll_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"))
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    percentage: Mapped[float] = mapped_column(Float)

    # Relationships
    poll: Mapped[Poll] = relationship("Poll", back_populates="results")
    party: Mapped[Party] = relationship("Party", back_populates="poll_results")

    __table_args__ = (UniqueConstraint("poll_id", "party_id", name="uix_poll_party"),)


class PipelineRun(Base):
    """Audit log for each pipeline:run execution.

    Stores timing, success/failure, and high-level statistics so you can
    review run history without parsing log files.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Unique identifier (UUID string) for cross-referencing with log lines
    run_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)

    # Timing
    started_at: Mapped[DateTimeType] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[DateTimeType] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    # Outcome
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scraper stats
    scrapers_run: Mapped[int] = mapped_column(Integer, default=0)
    scrapers_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    scrapers_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_scraped_polls: Mapped[int] = mapped_column(Integer, default=0)

    # ETL / cleaner stats
    etl_processed: Mapped[int] = mapped_column(Integer, default=0)
    etl_created: Mapped[int] = mapped_column(Integer, default=0)
    etl_updated: Mapped[int] = mapped_column(Integer, default=0)
    etl_skipped: Mapped[int] = mapped_column(Integer, default=0)
    etl_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Export stats
    export_polls: Mapped[int] = mapped_column(Integer, default=0)
    export_poll_results: Mapped[int] = mapped_column(Integer, default=0)
    export_raw_polls: Mapped[int] = mapped_column(Integer, default=0)

    # Archive (optional)
    archive_created: Mapped[bool] = mapped_column(Boolean, default=False)
    archive_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
