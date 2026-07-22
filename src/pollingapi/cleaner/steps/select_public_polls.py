"""Select the cleaned polls served by the default public dataset."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from pollingapi.cleaner.steps.link_matching_polls import MATCHED, MULTIPLE_MATCHES, NO_MATCH
from pollingapi.data_validation.config import (
    PublicDatasetSelectionConfig,
    get_validation_config,
)
from pollingapi.logging_config import get_logger
from pollingapi.models import Poll

logger = get_logger(__name__)

MISSING_PUBLISH_DATE = "missing_publish_date"
MISSING_PROVIDER = "missing_provider"
NON_PRIMARY_PROVIDER_BEFORE_CUTOFF = "non_primary_provider_before_cutoff"
NON_PUBLIC_PROVIDER_AFTER_CUTOFF = "non_public_provider_after_cutoff"
MATCHED_SECONDARY_PROVIDER = "matched_secondary_provider"
AMBIGUOUS_SECONDARY_PROVIDER = "ambiguous_secondary_provider"
UNMATCHED_SECONDARY_DISABLED = "unmatched_secondary_disabled"
SECONDARY_MATCH_NOT_RESOLVED = "secondary_match_not_resolved"


@dataclass(frozen=True)
class PublicPollSelectionStats:
    """Statistics for a public-poll selection run."""

    public: int = 0
    excluded: int = 0


def select_public_polls(
    db: Session,
    config: PublicDatasetSelectionConfig | None = None,
) -> PublicPollSelectionStats:
    """Mark cleaned polls that belong to the default public dataset.

    This step only updates public-serving metadata. It does not create, delete,
    or merge cleaned polls.
    """
    config = config or get_validation_config().public_dataset.selection
    polls = db.query(Poll).options(joinedload(Poll.provider)).order_by(Poll.id).all()

    public = 0
    excluded = 0
    for poll in polls:
        is_public, reason = _public_decision(poll, config)
        poll.is_public = is_public
        poll.public_exclusion_reason = reason
        if is_public:
            public += 1
        else:
            excluded += 1

    db.flush()
    logger.info("Public poll selection complete: public=%s excluded=%s", public, excluded)
    return PublicPollSelectionStats(public=public, excluded=excluded)


def _public_decision(
    poll: Poll,
    config: PublicDatasetSelectionConfig,
) -> tuple[bool, str | None]:
    if poll.publish_date is None:
        return False, MISSING_PUBLISH_DATE
    if poll.provider is None:
        return False, MISSING_PROVIDER

    provider_name = _normalized_provider_name(poll.provider.name)
    pre_cutoff_provider = _normalized_provider_name(config.pre_cutoff_provider)
    post_cutoff_provider = _normalized_provider_name(config.post_cutoff_provider)
    secondary_provider = _normalized_provider_name(config.secondary_provider)

    if poll.publish_date.year < config.cutoff_year:
        if provider_name == pre_cutoff_provider:
            return True, None
        return False, NON_PRIMARY_PROVIDER_BEFORE_CUTOFF

    if provider_name == post_cutoff_provider:
        return True, None

    if provider_name == secondary_provider:
        return _secondary_provider_decision(poll, config)

    return False, NON_PUBLIC_PROVIDER_AFTER_CUTOFF


def _secondary_provider_decision(
    poll: Poll,
    config: PublicDatasetSelectionConfig,
) -> tuple[bool, str | None]:
    if poll.matching_status == NO_MATCH and config.include_unmatched_secondary_after_cutoff:
        return True, None
    if poll.matching_status == MULTIPLE_MATCHES and config.exclude_ambiguous_secondary:
        return False, AMBIGUOUS_SECONDARY_PROVIDER
    if poll.matching_status == NO_MATCH:
        return False, UNMATCHED_SECONDARY_DISABLED
    if poll.matching_status == MATCHED:
        return False, MATCHED_SECONDARY_PROVIDER
    return False, SECONDARY_MATCH_NOT_RESOLVED


def _normalized_provider_name(value: str) -> str:
    return value.strip().casefold()
