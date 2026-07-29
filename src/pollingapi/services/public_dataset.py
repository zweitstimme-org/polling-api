"""Public dataset filtering policy."""

from sqlalchemy import extract, func, or_

from pollingapi.data_validation.config import PublicDatasetConfig
from pollingapi.models import Poll, PollValidation, Provider


def apply_public_dataset_policy(query, policy: PublicDatasetConfig):
    """Apply the final public-serving dataset gate to a poll/result query."""
    query = query.filter(Poll.is_public.is_(True))
    prevalidated = Poll.provider.has(
        func.lower(Provider.name) == policy.selection.pre_cutoff_provider.lower()
    ) & (extract("year", Poll.publish_date) < policy.selection.cutoff_year)

    query = query.outerjoin(Poll.validation)

    if policy.include_valid:
        if policy.require_persisted_validation:
            query = query.filter(or_(prevalidated, PollValidation.valid.is_(True)))
        else:
            query = query.filter(
                or_(prevalidated, PollValidation.id.is_(None), PollValidation.valid.is_(True))
            )
    else:
        query = query.filter(PollValidation.valid.is_(False))

    if not policy.include_warnings:
        query = query.filter(or_(prevalidated, PollValidation.warning_count == 0))

    for check_name in policy.exclude_failed_checks:
        column = getattr(PollValidation, check_name, None)
        if column is None:
            raise ValueError(f"Unknown public dataset validation check: {check_name}")
        query = query.filter(or_(prevalidated, column.is_(True)))

    return query
