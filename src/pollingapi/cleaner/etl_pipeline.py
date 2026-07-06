"""Main ETL pipeline for cleaning raw poll data.

This pipeline:
1. Reads from polls_raw table (never modifies it)
2. Normalizes data using declared datamodel definitions
3. Inserts cleaned data into polls and poll_results tables
"""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from pollingapi.cleaner.fingerprint import build_poll_fingerprint
from pollingapi.cleaner.transforms.dates import normalize_publish_date, normalize_survey_dates
from pollingapi.cleaner.transforms.references import (
    normalized_scope,
    resolve_institute,
    resolve_method,
    resolve_state,
)
from pollingapi.cleaner.transforms.respondents import parse_respondents
from pollingapi.cleaner.transforms.results import parse_party_results
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
from pollingapi.scraper.datamodel import (
    ElectionScope,
    GermanState,
    enum_key,
    party_short_name,
)
from pollingapi.scraper.datamodel import (
    PartyResult as DomainPartyResult,
)

logger = get_logger(__name__)


def normalize_raw_respondents_and_zeitraum(raw_poll: RawPoll) -> tuple[str | None, str | None]:
    """Return cleaner-facing respondents and timeframe without mutating RawPoll."""
    respondents = (raw_poll.respondents or "").strip() or None
    zeitraum = (raw_poll.zeitraum or "").strip() or None

    if not respondents and zeitraum and looks_like_respondent_count(zeitraum):
        return zeitraum, None

    return respondents, zeitraum


def looks_like_respondent_count(value: str) -> bool:
    """Return True when a raw text field contains only a respondent count."""
    compact = value.replace(" ", "")
    if not compact:
        return False
    if any(sep in compact for sep in ("-", "–", "/")):
        return False
    return re.fullmatch(r"\d+(?:[\.,]\d+)*", compact) is not None


@dataclass
class CleaningStats:
    """Statistics for cleaning run."""

    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


def get_or_create_institute(db: Session, name: str) -> Institute:
    """Get or create institute by canonical datamodel key."""
    institute_definition = resolve_institute(name)
    institute_key = enum_key(institute_definition)

    institute = db.query(Institute).filter(Institute.key == institute_key).first()
    if institute:
        return institute

    institute = Institute(key=institute_key, name=institute_definition.value)
    db.add(institute)
    db.flush()
    logger.debug(f"Created institute: {institute_key} - {name}")
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
    """Get or create method by canonical datamodel key.

    Returns None only if the method cannot be determined and should stay NULL.
    """
    method_definition = resolve_method(name)
    method_key = enum_key(method_definition)

    method = db.query(Method).filter(Method.key == method_key).first()
    if method:
        return method

    method = Method(key=method_key, name=method_definition.value)
    db.add(method)
    db.flush()
    logger.debug(f"Created method: {method_key} - {name}")
    return method


def get_or_create_election(db: Session, scope: str) -> Election:
    """Get or create election/scope reference row by canonical state key."""
    state = resolve_state(scope)
    election_key = enum_key(state)

    election = db.query(Election).filter(Election.key == election_key).first()
    if election:
        return election

    election_type = (
        ElectionScope.BUNDESTAGSWAHL.value
        if state in {GermanState.BUND, GermanState.OST, GermanState.WEST}
        else ElectionScope.LANDTAGSWAHL.value
    )

    election = Election(
        key=election_key,
        election_type=election_type,
        scope=normalized_scope(scope),
    )
    db.add(election)
    db.flush()
    logger.debug(f"Created election: {election_key} - {election_type}")
    return election


def find_existing_poll(
    db: Session,
    raw_id: int,
) -> Poll | None:
    """Find existing cleaned poll for a raw row.

    ``polls_raw`` is immutable, so the stable idempotency key for cleaning is
    ``RawPoll.id`` -> ``Poll.raw_id``. This avoids collapsing distinct raw rows
    that share publish date, institute, provider, and scope.
    """
    return db.query(Poll).filter(Poll.raw_id == raw_id).first()


def find_existing_poll_by_fingerprint(db: Session, fingerprint: str) -> Poll | None:
    """Find an existing cleaned poll by deterministic cleaned fingerprint."""
    return db.query(Poll).filter(Poll.fingerprint == fingerprint).first()


def _results_by_party_key(results: list[DomainPartyResult]) -> dict[str, float]:
    return {enum_key(result.party): result.value for result in results}


def _poll_results_by_party_key(poll: Poll) -> dict[str, float]:
    return {result.party_key: result.percentage for result in poll.results}


def _build_existing_poll_fingerprint(poll: Poll) -> str | None:
    results = _poll_results_by_party_key(poll)
    if not results:
        return None
    return build_poll_fingerprint(
        publish_date=poll.publish_date,
        survey_date_start=poll.survey_date_start,
        survey_date_end=poll.survey_date_end,
        respondents=poll.respondents,
        institute_key=poll.institute_key,
        provider_name=poll.provider.name if poll.provider else None,
        source=poll.source,
        method_key=poll.method_key,
        election_key=poll.election_key,
        scope=poll.scope,
        results=results,
    )


def backfill_missing_poll_fingerprints(db: Session) -> int:
    """Populate missing cleaned poll fingerprints without collapsing existing rows."""
    polls = (
        db.query(Poll)
        .options(joinedload(Poll.provider), joinedload(Poll.results))
        .filter(Poll.fingerprint.is_(None))
        .order_by(Poll.id)
        .all()
    )
    existing_fingerprints = {
        value for (value,) in db.query(Poll.fingerprint).filter(Poll.fingerprint.is_not(None)).all()
    }
    updated = 0

    for poll in polls:
        fingerprint = _build_existing_poll_fingerprint(poll)
        if not fingerprint or fingerprint in existing_fingerprints:
            continue
        poll.fingerprint = fingerprint
        existing_fingerprints.add(fingerprint)
        updated += 1

    if updated:
        db.flush()
        logger.info(f"Backfilled fingerprints for {updated} cleaned polls")
    return updated


def clean_single_poll(db: Session, raw_poll: RawPoll) -> tuple[Poll | None, bool]:
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

        respondents_raw, zeitraum_raw = normalize_raw_respondents_and_zeitraum(raw_poll)

        # Parse survey dates
        survey_start, survey_end, should_ignore = normalize_survey_dates(
            raw_poll.survey_date_start, raw_poll.survey_date_end, zeitraum_raw, publish_date
        )

        # Skip rows that should be ignored (election markers, etc.)
        if should_ignore:
            logger.debug(
                f"Skipping raw poll {raw_poll.id}: zeitraum indicates ignorable row ({raw_poll.zeitraum})"
            )
            return None, False

        # Parse respondents
        respondents_result = parse_respondents(respondents_raw, raw_poll.publish_date)
        respondents_count = respondents_result.count

        parsed_results = parse_party_results(raw_poll.parties)
        for failed_entry in parsed_results.failed_entries:
            logger.debug(
                "Skipping party result in raw poll %s: %s",
                raw_poll.id,
                failed_entry.parse_error,
            )
        if parsed_results.parse_error:
            logger.debug(
                "Skipping raw poll %s party payload issue: %s",
                raw_poll.id,
                parsed_results.parse_error,
            )
        valid_results = parsed_results.party_results
        if not valid_results:
            logger.debug(f"Skipping raw poll {raw_poll.id}: no valid party results")
            return None, False

        if not survey_start and respondents_result.date_start:
            survey_start = normalize_publish_date(respondents_result.date_start)
        if not survey_end and respondents_result.date_end:
            survey_end = normalize_publish_date(respondents_result.date_end)

        # Map foreign keys using declared datamodel definitions
        institute = get_or_create_institute(db, raw_poll.institute_id or "")
        provider = get_or_create_provider(db, raw_poll.provider or "")

        # Determine method
        method_hint = respondents_result.method_hint or raw_poll.method_id
        method = get_or_create_method(db, method_hint or "")

        # Classify election/scope using declared datamodel definitions
        election = get_or_create_election(db, raw_poll.scope or "")
        canonical_scope = normalized_scope(raw_poll.scope)
        method_key = method.key if method else None
        results_by_party_key = _results_by_party_key(valid_results)
        fingerprint = build_poll_fingerprint(
            publish_date=publish_date,
            survey_date_start=survey_start,
            survey_date_end=survey_end,
            respondents=respondents_count,
            institute_key=institute.key,
            provider_name=provider.name,
            source=raw_poll.source,
            method_key=method_key,
            election_key=election.key,
            scope=canonical_scope,
            results=results_by_party_key,
        )

        existing = find_existing_poll(db, raw_poll.id)

        if existing:
            poll = existing
            is_new = False
            logger.debug(f"Updating existing poll: {poll.id}")
        else:
            duplicate = find_existing_poll_by_fingerprint(db, fingerprint)
            if duplicate:
                raw_poll.duplicate_of_poll_id = duplicate.id
                db.flush()
                logger.info(
                    "Skipping raw poll %s: duplicate of cleaned poll %s by fingerprint",
                    raw_poll.id,
                    duplicate.public_id or duplicate.id,
                )
                return None, False

            poll = Poll()
            is_new = True
            logger.debug(f"Creating new poll from raw_id: {raw_poll.id}")

        # Set fields
        poll.raw_id = raw_poll.id
        poll.publish_date = publish_date
        poll.survey_date_start = survey_start
        poll.survey_date_end = survey_end
        poll.respondents = respondents_count
        poll.institute_key = institute.key
        poll.provider_id = provider.id
        poll.method_key = method_key
        poll.election_key = election.key
        poll.source = raw_poll.source
        poll.scope = canonical_scope
        poll.fingerprint = fingerprint

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

        sync_poll_results(db, poll, valid_results)

        return poll, is_new

    except Exception as e:
        logger.error(f"Error cleaning raw poll {raw_poll.id}: {e}", exc_info=True)
        raise


def sync_poll_results(db: Session, poll: Poll, results_data: list[DomainPartyResult]) -> None:
    """Sync party results for a poll using canonical party enum keys.

    Args:
        db: Database session
        poll: Poll object
        results_data: Canonical party result objects
    """
    # Query database directly for existing results to avoid relationship caching issues
    from pollingapi.models import PollResult as PollResultModel

    existing_results = {
        r.party_key: r
        for r in db.query(PollResultModel).filter(PollResultModel.poll_id == poll.id).all()
    }
    processed_parties = set()

    for result in results_data:
        party_key = enum_key(result.party)
        processed_parties.add(party_key)

        # Ensure party exists in database
        party = db.query(Party).filter(Party.key == party_key).first()
        if not party:
            party = Party(
                key=party_key,
                name=result.party.value,
                short_name=party_short_name(result.party),
            )
            db.add(party)
            db.flush()
            logger.debug(f"Created party: {party_key} - {party.name}")

        # Update or create result
        if party_key in existing_results:
            # Update existing
            existing_results[party_key].percentage = result.value
            logger.debug(f"Updated result for party {party_key}: {result.value}%")
        else:
            # Create new
            poll_result = PollResult(poll_id=poll.id, party_key=party_key, percentage=result.value)
            db.add(poll_result)
            logger.debug(f"Created result for party {party_key}: {result.value}%")

    stale_party_keys = set(existing_results) - processed_parties
    if stale_party_keys:
        (
            db.query(PollResultModel)
            .filter(PollResultModel.poll_id == poll.id)
            .filter(PollResultModel.party_key.in_(stale_party_keys))
            .delete(synchronize_session=False)
        )


def run_cleaning_pipeline(
    db: Session,
    limit: int | None = None,
    dry_run: bool = False,
    reprocess: bool = False,
    rebuild: bool = False,
) -> dict[str, int]:
    """Run the full cleaning pipeline.

    Args:
        db: Database session
        limit: Maximum number of rows to process
        dry_run: If True, don't commit changes
        reprocess: If True, process all raw rows even if a cleaned poll exists
        rebuild: If True, delete cleaned/reference rows and rebuild from raw rows

    Returns:
        Statistics dictionary
    """
    stats = CleaningStats()

    logger.info("Starting cleaning pipeline")

    if rebuild:
        logger.info("Rebuilding cleaned poll tables from immutable raw rows")
        db.query(PollResult).delete(synchronize_session=False)
        db.query(Poll).delete(synchronize_session=False)
        db.query(Institute).delete(synchronize_session=False)
        db.query(Provider).delete(synchronize_session=False)
        db.query(Election).delete(synchronize_session=False)
        db.query(Method).delete(synchronize_session=False)
        db.query(Party).delete(synchronize_session=False)
        db.flush()
    elif not dry_run:
        backfill_missing_poll_fingerprints(db)

    # Get unprocessed raw polls (not yet linked to a cleaned poll)
    if reprocess or rebuild:
        query = db.query(RawPoll).order_by(RawPoll.id)
    else:
        query = (
            db.query(RawPoll)
            .outerjoin(Poll, Poll.raw_id == RawPoll.id)
            .filter(Poll.id.is_(None))
            .filter(RawPoll.duplicate_of_poll_id.is_(None))
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
