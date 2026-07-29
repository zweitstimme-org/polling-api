from pollingapi.api.public_names import public_election_key, public_election_name
from pollingapi.models import Election


def test_public_election_names_cover_federal_state_and_european() -> None:
    assert public_election_key("BUND") == "federal"
    assert public_election_key("BB") == "bb"
    assert public_election_key("EU_WAHLEN") == "european"
    assert public_election_name(Election(key="BB", election_type="Landtagswahl")) == (
        "State election"
    )
    assert public_election_name(Election(key="EU_WAHLEN", election_type="Europawahl")) == (
        "European election"
    )
