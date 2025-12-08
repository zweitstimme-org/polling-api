from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class RawPolls(Base):
    __tablename__ = "polls_raw"

    id = Column(Integer, primary_key=True, autoincrement=True)
    publish_date = Column(String(50))
    respondents = Column(String(255))
    Zeitraum = Column(String(255))
    survey_date_start = Column(String(255))
    survey_date_end = Column(String(255))
    parties = Column(Text)
    institute_id = Column(String(255))
    provider = Column(String(255))
    tasker = Column(String(255))
    source = Column(String(255))
    scope = Column(String(50))
    election_id = Column(String(255))
    method_id = Column(String(255))
    date_downloaded = Column(String(50))
    inserted_at = Column(DateTime, default=datetime.now(timezone.utc))

    cleaned_poll = relationship("Poll", back_populates="raw_poll", uselist=False)


class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_id = Column(Integer, ForeignKey("polls_raw.id"), unique=True)
    publish_date = Column(Date)
    survey_date_start = Column(Date)
    survey_date_end = Column(Date)
    respondents = Column(Integer)
    scope = Column(String(50))
    date_cleaned = Column(DateTime, default=datetime.now(timezone.utc))

    institute_id = Column(Integer, ForeignKey("institutes.id"))
    provider_id = Column(Integer, ForeignKey("providers.id"))
    election_id = Column(Integer, ForeignKey("elections.id"))
    method_id = Column(Integer, ForeignKey("methods.id"))

    raw_poll = relationship("RawPolls", back_populates="cleaned_poll")
    institute = relationship("Institute", back_populates="polls")
    provider = relationship("Provider", back_populates="polls")
    election = relationship("Election", back_populates="polls")
    method = relationship("Method", back_populates="polls")
    results = relationship(
        "PollResult",
        back_populates="poll",
        cascade="all, delete-orphan",
    )


class PollResult(Base):
    __tablename__ = "poll_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    raw_id = Column(Integer, ForeignKey("polls_raw.id"))
    party_id = Column(Integer, ForeignKey("parties.id"))
    percentage = Column(Float)

    poll = relationship("Poll", back_populates="results")
    party = relationship("Party", back_populates="results")

    __table_args__ = (
        UniqueConstraint("poll_id", "party_id", name="_poll_party_uc"),
        UniqueConstraint("raw_id", "party_id", name="_raw_poll_party_uc"),
    )


class Institute(Base):
    __tablename__ = "institutes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)
    abbreviation = Column(String(50))

    polls = relationship("Poll", back_populates="institute")


class Party(Base):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)
    abbreviation = Column(String(10), unique=True)
    color = Column(String(7), nullable=True)

    results = relationship("PollResult", back_populates="party")


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)
    url = Column(String(255), nullable=True)

    polls = relationship("Poll", back_populates="provider")


class Tasker(Base):
    __tablename__ = "taskers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)


class Election(Base):
    __tablename__ = "elections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50))
    year = Column(Integer)
    state = Column(String(50), nullable=True)

    polls = relationship("Poll", back_populates="election")


class Method(Base):
    __tablename__ = "methods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    description = Column(Text, nullable=True)

    polls = relationship("Poll", back_populates="method")
