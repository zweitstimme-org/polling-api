"""Main ETL pipeline for cleaning raw poll data.

This pipeline:
1. Reads from polls_raw table (never modifies it)
2. Normalizes data using JSON-based mappings
3. Inserts cleaned data into polls and poll_results tables
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from pollingapi.cleaner.json_mappings import (
    get_canonical_scope,
    get_canonical_scope_from_raw,
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

# Party IDs used for fuzzy dedup: CDU/CSU, SPD, Grüne (same values = same poll across sources)
DEDUP_PARTY_IDS = (1, 2, 4)  # CDU/CSU, SPD, Grüne
# CDU and CSU stored separately in some sources (101, 102) -> normalize to Union (1)
UNION_PARTY_IDS = (1, 101, 102)
DEDUP_DATE_TOLERANCE_DAYS = 2
DEDUP_PERCENTAGE_TOLERANCE = 0.1


def _current_percentages_for_dedup(parties_data: Dict[str, float]) -> Dict[int, float]:
    """Build party_id -> percentage for CDU/CSU, SPD, Grüne from raw parties_data (name -> %)."""
    result: Dict[int, float] = {}
    union_sum = 0.0
    for name, pct in parties_data.items():
        party_id = map_party(name)
        if party_id is None:
            continue
        if party_id in (101, 102):
            union_sum += float(pct)
        elif party_id == 1:
            union_sum += float(pct)
        elif party_id in (2, 4):
            result[party_id] = float(pct)
    if union_sum:
        result[1] = union_sum
    return result


def _existing_percentages_for_dedup(db: Session, poll_id: int) -> Dict[int, float]:
    """Load CDU/CSU, SPD, Grüne percentages from existing poll's PollResult rows."""
    rows = (
        db.query(PollResult.party_id, PollResult.percentage)
        .filter(PollResult.poll_id == poll_id)
        .filter(PollResult.party_id.in_(UNION_PARTY_IDS + (2, 4)))
        .all()
    )
    result: Dict[int, float] = {}
    union_sum = 0.0
    for party_id, pct in rows:
        if party_id in (1, 101, 102):
            union_sum += float(pct)
        elif party_id in (2, 4):
            result[party_id] = float(pct)
    if union_sum:
        result[1] = union_sum
    return result


def _percentages_match(
    current: Dict[int, float], existing: Dict[int, float], tolerance: float = 0.0
) -> bool:
    """True if CDU/CSU, SPD, Grüne all present in both and match within tolerance."""
    for pid in DEDUP_PARTY_IDS:
        if pid not in current or pid not in existing:
            return False
        if abs(current[pid] - existing[pid]) > tolerance:
            return False
    return True


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
    """Get or create election by scope using JSON mapping.

    Uses canonical scope so elections and polls share the same scope strings.
    """
    parliament_id = map_parliament(scope)
    canonical = get_canonical_scope(parliament_id)

    # Try to find existing by ID
    election = db.query(Election).filter(Election.id == parliament_id).first()
    if election:
        # Keep scope in sync with canonical (fixes old seeded data)
        if election.scope != canonical:
            election.scope = canonical
        return election

    # Determine election type from parliament_id
    if parliament_id == 0:
        election_type = "Bundestagswahl"
    elif parliament_id == 17:
        election_type = "Europawahl"
    else:
        election_type = "Landtagswahl"

    # Create new with canonical scope
    election = Election(
        id=parliament_id,
        election_type=election_type,
        scope=canonical,
    )
    db.add(election)
    db.flush()
    logger.debug(f"Created election: {parliament_id} - {election_type} - {canonical}")
    return election


def find_existing_poll(
    db: Session,
    publish_date: date | None,
    institute_id: int,
    scope: str,
    provider_id: int | None = None,
) -> Poll | None:
    """Find existing poll by exact (date, institute, scope)."""
    if not publish_date:
        return None

    query = (
        db.query(Poll)
        .filter(Poll.publish_date == publish_date)
        .filter(Poll.institute_id == institute_id)
        .filter(Poll.scope == scope)
    )
    if provider_id is not None:
        query = query.filter(Poll.provider_id == provider_id)
    return query.first()


def find_existing_poll_fuzzy(
    db: Session,
    publish_date: date | None,
    institute_id: int,
    scope: str,
    parties_data: Dict[str, float],
    date_tolerance_days: int = DEDUP_DATE_TOLERANCE_DAYS,
    percentage_tolerance: float = DEDUP_PERCENTAGE_TOLERANCE,
) -> Poll | None:
    """Find existing poll when date may be off by 1–2 days and CDU/SPD/Grüne match.

    Same institute (already mapped), same scope, publish_date within ±date_tolerance_days,
    and CDU/CSU, SPD, Grüne percentages match (within percentage_tolerance).
    Used to deduplicate the same poll from Wahlrecht vs DAWUM when dates differ slightly.
    """
    if not publish_date:
        return None

    current = _current_percentages_for_dedup(parties_data)
    if len(current) < 3 or not all(pid in current for pid in DEDUP_PARTY_IDS):
        return None

    date_lo = publish_date - timedelta(days=date_tolerance_days)
    date_hi = publish_date + timedelta(days=date_tolerance_days)
    candidates = (
        db.query(Poll)
        .filter(Poll.scope == scope)
        .filter(Poll.institute_id == institute_id)
        .filter(Poll.publish_date >= date_lo)
        .filter(Poll.publish_date <= date_hi)
        .order_by(Poll.publish_date.desc())
        .all()
    )

    for poll in candidates:
        existing = _existing_percentages_for_dedup(db, poll.id)
        if _percentages_match(current, existing, tolerance=percentage_tolerance):
            logger.debug(
                f"Fuzzy duplicate: poll {poll.id} (date={poll.publish_date}) matches "
                f"current (date={publish_date})"
            )
            return poll
    return None


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
        raw_publish_date = raw_poll.publish_date
        publish_date = normalize_publish_date(raw_publish_date)
        if not publish_date:
            logger.warning(
                "Skipping raw poll %s: no valid publish_date (raw value: %r, provider: %s, scope: %s)",
                raw_poll.id,
                raw_publish_date,
                raw_poll.provider or "",
                raw_poll.scope or "",
            )
            return None, False

        # Parse survey dates
        survey_start, survey_end, should_ignore = normalize_survey_dates(
            raw_poll.survey_date_start, raw_poll.survey_date_end, raw_poll.zeitraum, publish_date
        )

        # Skip rows that should be ignored (election markers, etc.)
        if should_ignore:
            logger.debug(
                f"Skipping raw poll {raw_poll.id}: zeitraum indicates ignorable row ({raw_poll.zeitraum})"
            )
            return None, False

        # Parse respondents
        respondents_result = parse_respondents(raw_poll.respondents or "")
        respondents_count = respondents_result.count

        # Map foreign keys using JSON mappings
        institute = get_or_create_institute(db, raw_poll.institute_id or "")
        provider = get_or_create_provider(db, raw_poll.provider or "")

        # Determine method
        method_hint = respondents_result.method_hint or raw_poll.method_id
        method = get_or_create_method(db, method_hint or "")

        # Classify election using JSON mapping; use canonical scope for consistency
        canonical_scope = get_canonical_scope_from_raw(raw_poll.scope or "")
        election = get_or_create_election(db, raw_poll.scope or "")

        parties_data = parse_parties_json(raw_poll.parties)

        # Cross-source dedup: fuzzy (date ±2 days, same institute/scope, CDU/SPD/Grüne match)
        existing = find_existing_poll_fuzzy(
            db, publish_date, institute.id, canonical_scope, parties_data
        )
        if existing is None:
            existing = find_existing_poll(
                db, publish_date, institute.id, canonical_scope, provider_id=None
            )

        if existing:
            # Prefer Wahlrecht over DAWUM (respondents, field period); don't overwrite
            existing_provider = db.query(Provider).filter(Provider.id == existing.provider_id).first()
            if (
                existing_provider
                and existing_provider.name
                and "Wahlrecht" in existing_provider.name
                and provider.name
                and "DAWUM" in provider.name
            ):
                logger.debug(
                    f"Skipping raw poll {raw_poll.id}: keeping Wahlrecht poll {existing.id} (not overwriting with DAWUM)"
                )
                return None, False
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
        poll.scope = canonical_scope

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

        # When updating a cross-source duplicate, replace results with current raw poll
        if not is_new:
            db.query(PollResult).filter(PollResult.poll_id == poll.id).delete()
            db.flush()

        # Sync poll results using JSON party mappings (parties_data already parsed above)
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
