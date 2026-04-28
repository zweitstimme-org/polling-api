"""Main ETL pipeline for cleaning raw poll data.

This pipeline:
1. Reads from polls_raw table (never modifies it)
2. Normalizes data using JSON-based mappings
3. Inserts cleaned data into polls and poll_results tables
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from pollingapi.cleaner.json_mappings import (
    get_institute_name,
    get_method_name,
    get_party_name,
    get_party_shortcut,
    map_institute,
    map_method,
    map_parliament,
    map_party,
    normalize_scope,
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

NON_RESULT_PARTY_NAMES = {
    "nichtwähler",
    "nicht-wähler",
    "nichtwähler/unentschl.",
    "nichtwähler/unentschlos.",
    "unent-schlossene",
    "unentschlossene",
    "summe",
    "quelle",
}


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


def parse_parties_json(parties_json: str | None) -> dict[str, float]:
    """Parse parties JSON string to dictionary."""
    if not parties_json:
        return {}
    try:
        return json.loads(parties_json)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse parties JSON: {parties_json[:100]}...")
        return {}


def parse_percentage(value: object) -> float | None:
    """Parse raw percentage values from scraper payloads.

    Raw rows are immutable and may contain display strings such as ``"4,5 %"``
    or placeholders such as ``"–"``. Return None for placeholders/unusable
    values so the cleaned result table only stores numeric party results.
    """
    if value is None:
        return None

    if isinstance(value, int | float):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    if text in {"-", "–", "—", "−"}:
        return None

    text = text.replace("\xa0", " ").replace("%", "").strip()
    text = text.replace(",", ".")

    range_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        start, end = range_match.groups()
        return (float(start) + float(end)) / 2

    matches = re.findall(r"\d+(?:\.\d+)?", text)
    if not matches:
        return None

    try:
        return sum(float(match) for match in matches)
    except ValueError:
        return None


def is_non_result_party_name(name: str) -> bool:
    """Return True for raw table columns that are metadata, not party results."""
    normalized = re.sub(r"\s+", " ", name.lower().strip())
    return normalized in NON_RESULT_PARTY_NAMES


def get_or_create_institute(db: Session, name: str) -> Institute:
    """Get or create institute by name using JSON mapping."""
    institute_id = map_institute(name)

    # Try to find existing
    institute = db.query(Institute).filter(Institute.id == institute_id).first()
    if institute:
        return institute

    # Create new with ID from JSON
    institute = Institute(id=institute_id, name=get_institute_name(institute_id, name))
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
    method = Method(id=method_id, name=get_method_name(method_id, name))
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
    canonical_scope = normalize_scope(scope)
    if parliament_id == 0:
        election_type = "Bundestagswahl"
    elif parliament_id == 17:
        election_type = "Europawahl"
    else:
        election_type = "Landtagswahl"

    # Create new with ID from JSON
    election = Election(
        id=parliament_id,
        election_type=election_type,
        scope=canonical_scope,
    )
    db.add(election)
    db.flush()
    logger.debug(f"Created election: {parliament_id} - {election_type}")
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


def build_valid_party_results(parties_data: dict[str, object]) -> dict[int, float]:
    """Map and parse raw party results into canonical party IDs and percentages."""
    results: dict[int, float] = {}
    for party_name, percentage in parties_data.items():
        if is_non_result_party_name(party_name):
            continue

        parsed_percentage = parse_percentage(percentage)
        if parsed_percentage is None:
            continue

        party_id = map_party(party_name)
        if party_id is None:
            continue

        results.setdefault(party_id, parsed_percentage)

    return results


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
        respondents_result = parse_respondents(respondents_raw or "")
        respondents_count = respondents_result.count

        parties_data = parse_parties_json(raw_poll.parties)
        valid_results = build_valid_party_results(parties_data)
        if not valid_results:
            logger.debug(f"Skipping raw poll {raw_poll.id}: no valid party results")
            return None, False

        # Map foreign keys using JSON mappings
        institute = get_or_create_institute(db, raw_poll.institute_id or "")
        provider = get_or_create_provider(db, raw_poll.provider or "")

        # Determine method
        method_hint = respondents_result.method_hint or raw_poll.method_id
        method = get_or_create_method(db, method_hint or "")

        # Classify election using JSON mapping
        election = get_or_create_election(db, raw_poll.scope or "")
        canonical_scope = normalize_scope(raw_poll.scope)

        # Check for duplicate (include provider to distinguish between sources)
        existing = find_existing_poll(db, raw_poll.id)

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

        # Sync poll results using JSON party mappings
        sync_poll_results(db, poll, valid_results)

        return poll, is_new

    except Exception as e:
        logger.error(f"Error cleaning raw poll {raw_poll.id}: {e}", exc_info=True)
        raise


def sync_poll_results(db: Session, poll: Poll, results_data: dict[int, float]) -> None:
    """Sync party results for a poll using JSON mappings.

    Args:
        db: Database session
        poll: Poll object
        results_data: Dict mapping canonical party IDs to percentages
    """
    # Query database directly for existing results to avoid relationship caching issues
    from pollingapi.models import PollResult as PollResultModel

    existing_results = {
        r.party_id: r
        for r in db.query(PollResultModel).filter(PollResultModel.poll_id == poll.id).all()
    }
    processed_parties = set()

    for party_id, parsed_percentage in results_data.items():
        processed_parties.add(party_id)

        # Ensure party exists in database
        party = db.query(Party).filter(Party.id == party_id).first()
        if not party:
            # Create party with ID from JSON
            party = Party(
                id=party_id,
                name=get_party_name(party_id),
                short_name=get_party_shortcut(party_id),
            )
            db.add(party)
            db.flush()
            logger.debug(f"Created party: {party_id} - {party.name}")

        # Update or create result
        if party_id in existing_results:
            # Update existing
            existing_results[party_id].percentage = parsed_percentage
            logger.debug(f"Updated result for party {party_id}: {parsed_percentage}%")
        else:
            # Create new
            poll_result = PollResult(
                poll_id=poll.id, party_id=party_id, percentage=parsed_percentage
            )
            db.add(poll_result)
            logger.debug(f"Created result for party {party_id}: {parsed_percentage}%")

    stale_party_ids = set(existing_results) - processed_parties
    if stale_party_ids:
        (
            db.query(PollResultModel)
            .filter(PollResultModel.poll_id == poll.id)
            .filter(PollResultModel.party_id.in_(stale_party_ids))
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

    # Get unprocessed raw polls (not yet linked to a cleaned poll)
    if reprocess or rebuild:
        query = db.query(RawPoll).order_by(RawPoll.id)
    else:
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
