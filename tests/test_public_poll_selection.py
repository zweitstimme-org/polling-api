"""Tests for selecting the public default polling dataset."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.cleaner.steps.link_matching_polls import MATCHED, MULTIPLE_MATCHES, NO_MATCH
from pollingapi.cleaner.steps.select_public_polls import (
    AMBIGUOUS_SECONDARY_PROVIDER,
    MATCHED_SECONDARY_PROVIDER,
    NON_PRIMARY_PROVIDER_BEFORE_CUTOFF,
    select_public_polls,
)
from pollingapi.data_validation.config import PublicDatasetSelectionConfig
from pollingapi.database import Base
from pollingapi.models import Poll, Provider


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
    matching_status: str | None = None,
) -> Poll:
    poll = Poll(
        publish_date=publish_date,
        provider_id=provider.id,
        matching_status=matching_status,
        is_public=True,
    )
    session.add(poll)
    session.flush()
    return poll


def _config() -> PublicDatasetSelectionConfig:
    return PublicDatasetSelectionConfig(
        cutoff_year=2005,
        pre_cutoff_provider="Kayser/Rehmert",
        post_cutoff_provider="wahlrecht.de",
        secondary_provider="DAWUM",
        include_unmatched_secondary_after_cutoff=True,
        exclude_ambiguous_secondary=True,
    )


def test_select_public_polls_applies_provider_priority_by_year(tmp_path):
    session = _session(tmp_path)
    kayser = _provider(session, "Kayser/Rehmert")
    wahlrecht = _provider(session, "wahlrecht.de")

    pre_cutoff_kayser = _poll(session, provider=kayser, publish_date=dt.date(2004, 12, 31))
    pre_cutoff_wahlrecht = _poll(session, provider=wahlrecht, publish_date=dt.date(2004, 12, 31))
    cutoff_wahlrecht = _poll(session, provider=wahlrecht, publish_date=dt.date(2005, 1, 1))
    post_cutoff_kayser = _poll(session, provider=kayser, publish_date=dt.date(2005, 1, 1))

    stats = select_public_polls(session, _config())

    assert stats.public == 2
    assert stats.excluded == 2
    assert pre_cutoff_kayser.is_public is True
    assert cutoff_wahlrecht.is_public is True
    assert pre_cutoff_wahlrecht.is_public is False
    assert pre_cutoff_wahlrecht.public_exclusion_reason == NON_PRIMARY_PROVIDER_BEFORE_CUTOFF
    assert post_cutoff_kayser.is_public is False


def test_select_public_polls_keeps_only_unmatched_secondary_after_cutoff(tmp_path):
    session = _session(tmp_path)
    dawum = _provider(session, "DAWUM")

    unmatched = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 1, 1),
        matching_status=NO_MATCH,
    )
    matched = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 1, 2),
        matching_status=MATCHED,
    )
    ambiguous = _poll(
        session,
        provider=dawum,
        publish_date=dt.date(2024, 1, 3),
        matching_status=MULTIPLE_MATCHES,
    )

    stats = select_public_polls(session, _config())

    assert stats.public == 1
    assert stats.excluded == 2
    assert unmatched.is_public is True
    assert matched.is_public is False
    assert matched.public_exclusion_reason == MATCHED_SECONDARY_PROVIDER
    assert ambiguous.is_public is False
    assert ambiguous.public_exclusion_reason == AMBIGUOUS_SECONDARY_PROVIDER
