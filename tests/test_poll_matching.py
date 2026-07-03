"""Tests for linking equivalent polls across providers."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.cleaner.steps.link_matching_polls import (
    MATCHED,
    MULTIPLE_MATCHES,
    NO_MATCH,
    link_matching_polls,
)
from pollingapi.data_validation.config import PollMatchingConfig
from pollingapi.database import Base
from pollingapi.models import Party, Poll, PollResult, Provider


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _provider(session, name: str) -> Provider:
    provider = Provider(name=name)
    session.add(provider)
    session.flush()
    return provider


def _poll(
    session,
    *,
    provider: Provider,
    publish_date: dt.date,
    cdu_csu: float,
    spd: float,
) -> Poll:
    poll = Poll(
        publish_date=publish_date,
        institute_key="FORSA",
        provider_id=provider.id,
        election_key="BUND",
        scope="federal",
    )
    session.add(poll)
    session.flush()
    session.add_all(
        [
            PollResult(poll_id=poll.id, party_key="CDU_CSU", percentage=cdu_csu),
            PollResult(poll_id=poll.id, party_key="SPD", percentage=spd),
        ]
    )
    session.flush()
    return poll


def _config(**overrides) -> PollMatchingConfig:
    values = {
        "date_window_days": 7,
        "primary_provider": "Wahlrecht.de",
        "secondary_provider": "DAWUM",
        "result_parties": ("CDU_CSU", "SPD"),
        "max_party_delta": 1.0,
        "max_total_delta": 1.5,
    }
    values.update(overrides)
    return PollMatchingConfig(**values)


def _seed_parties(session) -> None:
    session.add_all(
        [
            Party(key="CDU_CSU", name="CDU/CSU"),
            Party(key="SPD", name="SPD"),
        ]
    )
    session.flush()


def test_link_matching_polls_writes_bidirectional_links(tmp_path):
    session = _session(tmp_path)
    _seed_parties(session)
    wahlrecht = _provider(session, "Wahlrecht.de")
    dawum = _provider(session, "DAWUM")
    primary = _poll(
        session,
        provider=wahlrecht,
        publish_date=dt.date(2024, 6, 1),
        cdu_csu=30.0,
        spd=16.0,
    )
    secondary = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 6, 3),
        cdu_csu=30.5,
        spd=16.0,
    )

    stats = link_matching_polls(session, _config())
    session.flush()

    assert stats.matched_pairs == 1
    assert primary.matching_poll_id == secondary.id
    assert secondary.matching_poll_id == primary.id
    assert primary.matching_status == MATCHED
    assert secondary.matching_status == MATCHED


def test_link_matching_polls_marks_multiple_matches_without_linking(tmp_path):
    session = _session(tmp_path)
    _seed_parties(session)
    wahlrecht = _provider(session, "Wahlrecht.de")
    dawum = _provider(session, "DAWUM")
    primary = _poll(
        session,
        provider=wahlrecht,
        publish_date=dt.date(2024, 6, 1),
        cdu_csu=30.0,
        spd=16.0,
    )
    secondary_one = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 6, 2),
        cdu_csu=30.0,
        spd=16.0,
    )
    secondary_two = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 6, 3),
        cdu_csu=30.5,
        spd=16.0,
    )

    stats = link_matching_polls(session, _config())
    session.flush()

    assert stats.matched_pairs == 0
    assert stats.multiple_matches == 1
    assert primary.matching_poll_id is None
    assert primary.matching_status == MULTIPLE_MATCHES
    assert secondary_one.matching_poll_id is None
    assert secondary_one.matching_status == MULTIPLE_MATCHES
    assert secondary_two.matching_poll_id is None
    assert secondary_two.matching_status == MULTIPLE_MATCHES


def test_link_matching_polls_rejects_result_delta_above_threshold(tmp_path):
    session = _session(tmp_path)
    _seed_parties(session)
    wahlrecht = _provider(session, "Wahlrecht.de")
    dawum = _provider(session, "DAWUM")
    primary = _poll(
        session,
        provider=wahlrecht,
        publish_date=dt.date(2024, 6, 1),
        cdu_csu=30.0,
        spd=16.0,
    )
    secondary = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 6, 2),
        cdu_csu=31.0,
        spd=16.0,
    )

    stats = link_matching_polls(session, _config(max_party_delta=0.4, max_total_delta=0.4))
    session.flush()

    assert stats.matched_pairs == 0
    assert primary.matching_poll_id is None
    assert secondary.matching_poll_id is None
    assert primary.matching_status == NO_MATCH
    assert secondary.matching_status == NO_MATCH
