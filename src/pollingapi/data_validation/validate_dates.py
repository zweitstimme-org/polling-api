"""Validate poll date consistency."""

import datetime as dt

from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


def validate_dates(poll: Poll, today: dt.date | None = None) -> ValidationCheck:
    """Validate survey dates, publish date, and future dates."""
    today = today or dt.date.today()
    dates = [poll.survey_date_start, poll.survey_date_end, poll.publish_date]
    if any(value is None for value in dates):
        return ValidationCheck(
            passed=False,
            observed=_date_observation(poll),
            expected="survey_date_start <= survey_date_end <= publish_date; no future dates.",
            message="One or more required dates are missing.",
        )

    start = poll.survey_date_start
    end = poll.survey_date_end
    publish = poll.publish_date
    passed = start <= end <= publish and all(value <= today for value in dates if value)
    return ValidationCheck(
        passed=passed,
        observed=_date_observation(poll),
        expected="survey_date_start <= survey_date_end <= publish_date; no future dates.",
        message=None if passed else "Poll dates are inconsistent or in the future.",
    )


def _date_observation(poll: Poll) -> dict[str, str | None]:
    return {
        "survey_date_start": poll.survey_date_start.isoformat() if poll.survey_date_start else None,
        "survey_date_end": poll.survey_date_end.isoformat() if poll.survey_date_end else None,
        "publish_date": poll.publish_date.isoformat() if poll.publish_date else None,
    }
