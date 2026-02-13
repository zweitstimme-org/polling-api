"""Main ETL pipeline for cleaning raw poll data.

This pipeline:
1. Reads from polls_raw table (never modifies it)
2. Normalizes data using JSON-based mappings
3. Inserts cleaned data into polls and poll_results tables
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from pollingapi.cleaner.json_mappings import (
    map_institute,
    map_method,
    map_parliament,
    map_party,
)
from pollingapi.cleaner.transforms.dates import normalize_publish_date, normalize_survey_dates
from pollingapi.cleaner.transforms.respondents import parse_respondents
from pollingapi.logging_config import get_logger
from pollingapi.models import (
    Election,
    Institute,
    Method,
    Party,
    Poll,
    PollResult,
    Provider,
    RawPoll,
)

logger = get_logger(__name__)


@dataclass
class CleaningStats:
    """Statistics for cleaning run."""

    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


def parse_parties_json(parties_json: str | None) -> Dict[str, float]:
    """Parse parties JSON string to dictionary."""
    if not parties_json:
        return {}
    try:
        return json.loads(parties_json)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse parties JSON: {parties_json[:100]}...")
        return {}


def get_or_create_institute(db: Session, name: str) -> Institute:
    """Get or create institute by name using JSON mapping."""
    institute_id = map_institute(name)

    # Try to find existing
    institute = db.query(Institute).filter(Institute.id == institute_id).first()
    if institute:
        return institute

    # Create new with ID from JSON
    institute = Institute(id=institute_id, name=name or "Unknown")
    db.add(institute)
    db.flush()
    logger.debug(f"Created institute: {institute_id} - {name}")
    return institute


def get_or_create_provider(db: Session, name: str) -> Provider:
    """Get or create provider by name."""
    # Normalize name
    normalized_name = name or "Unknown"

    # Providers don't have JSON mappings, use simple lookup
    provider = db.query(Provider).filter(Provider.name == normalized_name).first()
    if provider:
        return provider

    # Create new (auto-increment ID)
    provider = Provider(name=normalized_name)
    db.add(provider)
    db.flush()
    logger.debug(f"Created provider: {provider.id} - {normalized_name}")
    return provider


def get_or_create_method(db: Session, name: str | None) -> Method | None:
    """Get or create method by name using JSON mapping.

    Returns None if method cannot be determined.
    """
    if not name:
        return None

    method_id = map_method(name)

    # If method is unknown, return None (will be stored as NULL in DB)
    if method_id is None:
        return None

    # Try to find existing
    method = db.query(Method).filter(Method.id == method_id).first()
    if method:
        return method

    # Create new with ID from JSON
    method = Method(id=method_id, name=name)
    db.add(method)
    db.flush()
    logger.debug(f"Created method: {method_id} - {name}")
    return method


def get_or_create_election(db: Session, scope: str) -> Election:
    """Get or create election by scope using JSON mapping."""
    parliament_id = map_parliament(scope)

    # Try to find existing by ID
    election = db.query(Election).filter(Election.id == parliament_id).first()
    if election:
        return election

    # Determine election type from scope
    scope_lower = (scope or "").lower()
    if scope_lower == "federal" or parliament_id == 0:
        election_type = "Bundestagswahl"
    elif parliament_id == 17:
        election_type = "Europawahl"
    else:
        election_type = "Landtagswahl"

    # Create new with ID from JSON
    election = Election(
        id=parliament_id,
        election_type=election_type,
        scope=scope_lower if scope else None,
    )
    db.add(election)
    db.flush()
    logger.debug(f"Created election: {parliament_id} - {election_type}")
    return election


def find_existing_poll(
    db: Session, publish_date: date | None, institute_id: int, scope: str, provider_id: int
) -> Poll | None:
    """Find existing poll by key fields (including provider for uniqueness)."""
    if not publish_date:
        return None

    return (
        db.query(Poll)
        .filter(Poll.publish_date == publish_date)
        .filter(Poll.institute_id == institute_id)
        .filter(Poll.scope == scope)
        .filter(Poll.provider_id == provider_id)
        .first()
    )


def clean_single_poll(db: Session, raw_poll: RawPoll) -> Tuple[Poll | None, bool]:
    """Clean a single raw poll and return cleaned poll.

    Args:
        db: Database session
        raw_poll: Raw poll from database

    Returns:
        Tuple of (cleaned Poll or None, is_new boolean)
    """
    try:
        # Parse dates
        publish_date = normalize_publish_date(raw_poll.publish_date)
        if not publish_date:
            logger.warning(f"Skipping raw poll {raw_poll.id}: no valid publish_date")
            return None, False

        # Parse survey dates
        survey_start, survey_end = normalize_survey_dates(
            raw_poll.survey_date_start, raw_poll.survey_date_end, raw_poll.zeitraum, publish_date
        )

        # Parse respondents
        respondents_result = parse_respondents(raw_poll.respondents or "")
        respondents_count = respondents_result.count

        # Map foreign keys using JSON mappings
        institute = get_or_create_institute(db, raw_poll.institute_id or "")
        provider = get_or_create_provider(db, raw_poll.provider or "")

        # Determine method
        method_hint = respondents_result.method_hint or raw_poll.method_id
        method = get_or_create_method(db, method_hint or "")

        # Classify election using JSON mapping
        election = get_or_create_election(db, raw_poll.scope or "")

        # Check for duplicate (include provider to distinguish between sources)
        existing = find_existing_poll(
            db, publish_date, institute.id, raw_poll.scope or "", provider.id
        )

        if existing:
            poll = existing
            is_new = False
            logger.debug(f"Updating existing poll: {poll.id}")
        else:
            poll = Poll()
            is_new = True
            logger.debug(f"Creating new poll from raw_id: {raw_poll.id}")

        # Set fields
        poll.raw_id = raw_poll.id
        poll.publish_date = publish_date
        poll.survey_date_start = survey_start
        poll.survey_date_end = survey_end
        poll.respondents = respondents_count
        poll.institute_id = institute.id
        poll.provider_id = provider.id
        poll.method_id = method.id if method else None
        poll.election_id = election.id
        poll.source = raw_poll.source
        poll.scope = raw_poll.scope

        # Parse date downloaded
        if raw_poll.date_downloaded:
            try:
                poll.date_downloaded = datetime.fromisoformat(
                    raw_poll.date_downloaded.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                poll.date_downloaded = None

        db.add(poll)
        db.flush()

        # Sync poll results using JSON party mappings
        parties_data = parse_parties_json(raw_poll.parties)
        sync_poll_results(db, poll, parties_data)

        return poll, is_new

    except Exception as e:
        logger.error(f"Error cleaning raw poll {raw_poll.id}: {e}", exc_info=True)
        raise


def sync_poll_results(db: Session, poll: Poll, parties_data: Dict[str, float]) -> None:
    """Sync party results for a poll using JSON mappings.

    Args:
        db: Database session
        poll: Poll object
        parties_data: Dict mapping party names to percentages
    """
    # Query database directly for existing results to avoid relationship caching issues
    from pollingapi.models import PollResult as PollResultModel

    existing_results = {
        r.party_id: r
        for r in db.query(PollResultModel).filter(PollResultModel.poll_id == poll.id).all()
    }
    processed_parties = set()

    for party_name, percentage in parties_data.items():
        # Map party name to ID using JSON
        party_id = map_party(party_name)

        if party_id is None:
            logger.debug(f"Unknown party '{party_name}' in poll {poll.id}, skipping")
            continue

        # Skip if already processed (avoid duplicates)
        if party_id in processed_parties:
            continue
        processed_parties.add(party_id)

        # Ensure party exists in database
        party = db.query(Party).filter(Party.id == party_id).first()
        if not party:
            # Create party with ID from JSON
            party = Party(id=party_id, name=party_name)
            db.add(party)
            db.flush()
            logger.debug(f"Created party: {party_id} - {party_name}")

        # Update or create result
        if party_id in existing_results:
            # Update existing
            existing_results[party_id].percentage = float(percentage)
            logger.debug(f"Updated result for party {party_id}: {percentage}%")
        else:
            # Create new
            poll_result = PollResult(
                poll_id=poll.id, party_id=party_id, percentage=float(percentage)
            )
            db.add(poll_result)
            logger.debug(f"Created result for party {party_id}: {percentage}%")


def run_cleaning_pipeline(
    db: Session, limit: int | None = None, dry_run: bool = False
) -> Dict[str, int]:
    """Run the full cleaning pipeline.

    Args:
        db: Database session
        limit: Maximum number of rows to process
        dry_run: If True, don't commit changes

    Returns:
        Statistics dictionary
    """
    stats = CleaningStats()

    logger.info("Starting cleaning pipeline")

    # Get unprocessed raw polls (not yet linked to a cleaned poll)
    query = (
        db.query(RawPoll)
        .outerjoin(Poll, Poll.raw_id == RawPoll.id)
        .filter(Poll.id.is_(None))
        .order_by(RawPoll.id)
    )

    if limit:
        query = query.limit(limit)

    raw_polls = query.all()
    stats.processed = len(raw_polls)

    logger.info(f"Processing {len(raw_polls)} raw polls")

    for raw_poll in raw_polls:
        try:
            poll, is_new = clean_single_poll(db, raw_poll)

            if poll:
                if is_new:
                    stats.created += 1
                else:
                    stats.updated += 1
            else:
                stats.skipped += 1

        except Exception as e:
            logger.error(f"Failed to process raw poll {raw_poll.id}: {e}")
            stats.errors += 1

    if dry_run:
        logger.info("Dry run - rolling back changes")
        db.rollback()
    else:
        logger.info("Committing changes to database")
        db.commit()

    logger.info(
        f"Pipeline complete: processed={stats.processed}, "
        f"created={stats.created}, updated={stats.updated}, "
        f"skipped={stats.skipped}, errors={stats.errors}"
    )

    return {
        "processed": stats.processed,
        "created": stats.created,
        "updated": stats.updated,
        "skipped": stats.skipped,
        "errors": stats.errors,
    }
