"""Database seeding from declared domain models."""

from sqlalchemy.orm import Session

from pollingapi.models import Election, Institute, Method, Party
from pollingapi.scraper.datamodel import (
    ElectionScope,
    GermanState,
    SurveyMethod,
    enum_key,
    party_short_name,
)
from pollingapi.scraper.datamodel import (
    Institute as InstituteDefinition,
)
from pollingapi.scraper.datamodel import (
    Party as PartyDefinition,
)


def seed_institutes_from_datamodel(db: Session) -> int:
    """Seed institutes from the declared institute enum."""
    count = 0
    for definition in InstituteDefinition:
        existing = db.query(Institute).filter(Institute.key == enum_key(definition)).first()
        if not existing:
            db.add(Institute(key=enum_key(definition), name=definition.value))
            count += 1
        elif existing.name != definition.value:
            existing.name = definition.value
            count += 1
    db.commit()
    return count


def seed_methods_from_datamodel(db: Session) -> int:
    """Seed survey methods from the declared method enum."""
    count = 0
    for definition in SurveyMethod:
        existing = db.query(Method).filter(Method.key == enum_key(definition)).first()
        if not existing:
            db.add(Method(key=enum_key(definition), name=definition.value))
            count += 1
        elif existing.name != definition.value:
            existing.name = definition.value
            count += 1
    db.commit()
    return count


def seed_parties_from_datamodel(db: Session) -> int:
    """Seed parties from the declared party enum and short-handle mapping."""
    count = 0
    for definition in PartyDefinition:
        short_name = party_short_name(definition)
        existing = db.query(Party).filter(Party.key == enum_key(definition)).first()
        if not existing:
            db.add(
                Party(
                    key=enum_key(definition),
                    name=definition.value,
                    short_name=short_name,
                )
            )
            count += 1
            continue

        updated = False
        if existing.name != definition.value:
            existing.name = definition.value
            updated = True
        if existing.short_name != short_name:
            existing.short_name = short_name
            updated = True
        if updated:
            count += 1
    db.commit()
    return count


def _election_type_for_state(state: GermanState) -> str:
    if state in {GermanState.BUND, GermanState.OST, GermanState.WEST}:
        return ElectionScope.BUNDESTAGSWAHL.value
    return ElectionScope.LANDTAGSWAHL.value


def _scope_for_state(state: GermanState) -> str:
    if state is GermanState.BUND:
        return "federal"
    if state is GermanState.NW:
        return "nrw"
    return state.name.lower()


def seed_elections_from_datamodel(db: Session) -> int:
    """Seed election/scope reference rows from the declared state enum."""
    count = 0
    for state in GermanState:
        existing = db.query(Election).filter(Election.key == enum_key(state)).first()
        election_type = _election_type_for_state(state)
        scope = _scope_for_state(state)
        if not existing:
            db.add(
                Election(
                    key=enum_key(state),
                    election_type=election_type,
                    scope=scope,
                    year=None,
                    date=None,
                )
            )
            count += 1
            continue

        updated = False
        if existing.election_type != election_type:
            existing.election_type = election_type
            updated = True
        if existing.scope != scope:
            existing.scope = scope
            updated = True
        if updated:
            count += 1
    db.commit()
    return count


def seed_all_from_json(db: Session) -> dict[str, int]:
    """Seed all reference tables.

    The public function name is kept for CLI compatibility; the source of truth
    is now the declared datamodel instead of numeric JSON mapping files.
    """
    return {
        "institutes": seed_institutes_from_datamodel(db),
        "methods": seed_methods_from_datamodel(db),
        "parties": seed_parties_from_datamodel(db),
        "elections": seed_elections_from_datamodel(db),
    }
