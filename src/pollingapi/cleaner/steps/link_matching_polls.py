"""Link equivalent cleaned polls from different providers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session, joinedload

from pollingapi.data_validation.config import PollMatchingConfig, get_validation_config
from pollingapi.logging_config import get_logger
from pollingapi.models import Poll, PollResult, Provider

logger = get_logger(__name__)

MATCHED = "matched"
NO_MATCH = "no_match"
MULTIPLE_MATCHES = "multiple_matches"
MISSING_RESULTS = "missing_results"


@dataclass(frozen=True)
class PollMatchStats:
    """Statistics for a poll-linking run."""

    matched_pairs: int = 0
    no_match: int = 0
    multiple_matches: int = 0
    missing_results: int = 0


@dataclass(frozen=True)
class MatchCandidate:
    """Acceptable match candidate and its score."""

    primary: Poll
    secondary: Poll
    score: float


def link_matching_polls(db: Session, config: PollMatchingConfig | None = None) -> PollMatchStats:
    """Link matching Wahlrecht and DAWUM polls bidirectionally.

    Matching is intentionally conservative. A link is written only when exactly
    one primary poll and one secondary poll accept each other under the configured
    date and result thresholds. Ambiguous cases are marked and logged.
    """
    config = config or get_validation_config().poll_matching

    primary_polls = _provider_polls(db, config.primary_provider)
    secondary_polls = _provider_polls(db, config.secondary_provider)

    _clear_matching_state([*primary_polls, *secondary_polls])

    secondary_by_id = {poll.id: poll for poll in secondary_polls}
    accepted = _accepted_candidates(primary_polls, secondary_polls, config)
    by_primary = _group_by_primary(accepted)
    by_secondary = _group_by_secondary(accepted)

    matched_pairs = 0
    no_match = 0
    multiple_matches = 0
    missing_results = 0
    ambiguous_secondary_ids: set[int] = set()

    for primary in primary_polls:
        candidates = by_primary.get(primary.id, [])
        if not _has_required_results(primary, config.result_parties):
            primary.matching_status = MISSING_RESULTS
            missing_results += 1
            continue
        if not candidates:
            primary.matching_status = NO_MATCH
            no_match += 1
            continue

        conflicted_candidates = [
            candidate
            for candidate in candidates
            if len(by_secondary.get(candidate.secondary.id, [])) > 1
        ]
        if len(candidates) > 1 or conflicted_candidates:
            primary.matching_status = MULTIPLE_MATCHES
            multiple_matches += 1
            ambiguous_ids = [candidate.secondary.id for candidate in candidates]
            ambiguous_secondary_ids.update(ambiguous_ids)
            logger.warning(
                "Multiple matching polls for primary poll %s: secondary candidates=%s",
                primary.id,
                ambiguous_ids,
            )
            continue

        candidate = candidates[0]
        primary.matching_poll_id = candidate.secondary.id
        primary.matching_status = MATCHED
        candidate.secondary.matching_poll_id = primary.id
        candidate.secondary.matching_status = MATCHED
        matched_pairs += 1

    for secondary_id, candidates in by_secondary.items():
        if len(candidates) > 1:
            ambiguous_secondary_ids.add(secondary_id)
            logger.warning(
                "Secondary poll %s has multiple primary matches: primary candidates=%s",
                secondary_id,
                [candidate.primary.id for candidate in candidates],
            )

    for secondary_id in ambiguous_secondary_ids:
        secondary = secondary_by_id[secondary_id]
        secondary.matching_poll_id = None
        secondary.matching_status = MULTIPLE_MATCHES

    for secondary in secondary_polls:
        if secondary.matching_status:
            continue
        if not _has_required_results(secondary, config.result_parties):
            secondary.matching_status = MISSING_RESULTS
            missing_results += 1
        else:
            secondary.matching_status = NO_MATCH
            no_match += 1

    logger.info(
        "Poll matching complete: matched_pairs=%s no_match=%s multiple_matches=%s "
        "missing_results=%s",
        matched_pairs,
        no_match,
        multiple_matches,
        missing_results,
    )
    return PollMatchStats(
        matched_pairs=matched_pairs,
        no_match=no_match,
        multiple_matches=multiple_matches,
        missing_results=missing_results,
    )


def _provider_polls(db: Session, provider_name: str) -> list[Poll]:
    return (
        db.query(Poll)
        .join(Provider)
        .options(joinedload(Poll.results).joinedload(PollResult.party))
        .filter(Provider.name == provider_name)
        .filter(Poll.publish_date.is_not(None))
        .order_by(Poll.publish_date, Poll.id)
        .all()
    )


def _clear_matching_state(polls: list[Poll]) -> None:
    for poll in polls:
        poll.matching_poll_id = None
        poll.matching_status = None


def _accepted_candidates(
    primary_polls: list[Poll],
    secondary_polls: list[Poll],
    config: PollMatchingConfig,
) -> list[MatchCandidate]:
    accepted = []
    for primary in primary_polls:
        if not primary.publish_date or not _has_required_results(primary, config.result_parties):
            continue
        lower = primary.publish_date - timedelta(days=config.date_window_days)
        upper = primary.publish_date + timedelta(days=config.date_window_days)

        for secondary in secondary_polls:
            if not secondary.publish_date or not lower <= secondary.publish_date <= upper:
                continue
            if not _same_poll_context(primary, secondary):
                continue

            score = _result_delta(primary, secondary, config.result_parties)
            if score is None:
                continue
            max_party_delta = _max_party_delta(primary, secondary, config.result_parties)
            if max_party_delta > config.max_party_delta or score > config.max_total_delta:
                continue

            days_apart = abs((primary.publish_date - secondary.publish_date).days)
            accepted.append(
                MatchCandidate(
                    primary=primary,
                    secondary=secondary,
                    score=float(days_apart) + score,
                )
            )

    return sorted(accepted, key=lambda candidate: (candidate.score, candidate.secondary.id))


def _same_poll_context(primary: Poll, secondary: Poll) -> bool:
    if primary.scope != secondary.scope:
        return False
    if primary.institute_key != secondary.institute_key:
        return False
    return not (
        primary.election_key
        and secondary.election_key
        and primary.election_key != secondary.election_key
    )


def _group_by_primary(candidates: list[MatchCandidate]) -> dict[int, list[MatchCandidate]]:
    grouped: dict[int, list[MatchCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.primary.id].append(candidate)
    return grouped


def _group_by_secondary(candidates: list[MatchCandidate]) -> dict[int, list[MatchCandidate]]:
    grouped: dict[int, list[MatchCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.secondary.id].append(candidate)
    return grouped


def _has_required_results(poll: Poll, party_keys: tuple[str, ...]) -> bool:
    results = _result_map(poll)
    return all(party_key in results for party_key in party_keys)


def _result_delta(primary: Poll, secondary: Poll, party_keys: tuple[str, ...]) -> float | None:
    primary_results = _result_map(primary)
    secondary_results = _result_map(secondary)
    deltas = []
    for party_key in party_keys:
        if party_key not in primary_results or party_key not in secondary_results:
            return None
        deltas.append(abs(primary_results[party_key] - secondary_results[party_key]))
    return sum(deltas)


def _max_party_delta(primary: Poll, secondary: Poll, party_keys: tuple[str, ...]) -> float:
    primary_results = _result_map(primary)
    secondary_results = _result_map(secondary)
    return max(abs(primary_results[key] - secondary_results[key]) for key in party_keys)


def _result_map(poll: Poll) -> dict[str, float]:
    return {result.party_key: result.percentage for result in poll.results}
