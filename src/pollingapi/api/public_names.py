"""Public-facing names for internal reference values."""

from pollingapi.models import Election

ELECTION_KEY_MAP = {
    "BUND": "federal",
    "EU_WAHLEN": "european",
    "NW": "nrw",
}

ELECTION_NAME_MAP = {
    "Bundestagswahl": "Federal election",
    "Landtagswahl": "State election",
    "Europawahl": "European election",
}


def public_election_key(value: str | None) -> str | None:
    """Return the public English election key for an internal election key."""
    if value is None:
        return None
    return ELECTION_KEY_MAP.get(value, value.lower())


def public_election_name(election: Election | None) -> str | None:
    """Return the public English election name for an election row."""
    if election is None:
        return None
    return ELECTION_NAME_MAP.get(election.election_type, election.election_type)
