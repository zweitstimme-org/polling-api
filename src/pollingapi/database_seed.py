"""Database seeding from JSON files.

This module handles seeding reference tables from JSON files.
The JSON files in the json/ directory define the primary keys
that will be used for relations in the database.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from pollingapi.models import Election, Institute, Method, Party, Tasker


def load_json_data(filename: str) -> dict[str, Any]:
    """Load JSON data from the json directory."""
    # Find project root by looking for json/ directory
    current_dir = Path(__file__).parent

    # Search up the tree for the project root containing json/
    json_dir = None
    for parent in [current_dir] + list(current_dir.parents):
        potential_json_dir = parent / "json"
        if potential_json_dir.exists() and potential_json_dir.is_dir():
            json_dir = potential_json_dir
            break

    if json_dir is None:
        # Fallback: assume project root is 3 levels up from pollingapi/database_seed.py
        # src/pollingapi/database_seed.py -> project_root
        json_dir = current_dir.parent.parent / "json"

    file_path = json_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def seed_institutes_from_json(db: Session) -> int:
    """Seed institutes table from institutes.json.

    Uses the exact IDs from the JSON file as primary keys.
    """
    data = load_json_data("institutes.json")
    count = 0

    for institute_id_str, info in data.items():
        institute_id = int(institute_id_str)
        name = info.get("Name", f"Institute {institute_id}")

        existing = db.query(Institute).filter(Institute.id == institute_id).first()
        if not existing:
            institute = Institute(id=institute_id, name=name)
            db.add(institute)
            count += 1
        else:
            # Update name if it has changed
            if existing.name != name:
                existing.name = name
                count += 1

    db.commit()
    return count


def seed_methods_from_json(db: Session) -> int:
    """Seed methods table from methods.json.

    Uses the exact IDs from the JSON file as primary keys.
    """
    data = load_json_data("methods.json")
    count = 0

    for method_id_str, info in data.items():
        method_id = int(method_id_str)
        name = info.get("Name", f"Method {method_id}")

        existing = db.query(Method).filter(Method.id == method_id).first()
        if not existing:
            method = Method(id=method_id, name=name)
            db.add(method)
            count += 1
        else:
            # Update name if it has changed
            if existing.name != name:
                existing.name = name
                count += 1

    db.commit()
    return count


def seed_taskers_from_json(db: Session) -> int:
    """Seed taskers table from taskers.json.

    Uses the exact IDs from the JSON file as primary keys.
    """
    data = load_json_data("taskers.json")
    count = 0

    for tasker_id_str, info in data.items():
        tasker_id = int(tasker_id_str)
        name = info.get("Name", f"Tasker {tasker_id}")

        existing = db.query(Tasker).filter(Tasker.id == tasker_id).first()
        if not existing:
            tasker = Tasker(id=tasker_id, name=name)
            db.add(tasker)
            count += 1
        else:
            # Update name if it has changed
            if existing.name != name:
                existing.name = name
                count += 1

    db.commit()
    return count


def seed_parties_from_json(db: Session) -> int:
    """Seed parties table from parties.json.

    Uses the exact IDs from the JSON file as primary keys.
    """
    data = load_json_data("parties.json")
    count = 0

    for party_id_str, info in data.items():
        party_id = int(party_id_str)
        name = info.get("Name", f"Party {party_id}")
        short_name = info.get("Shortcut", "")

        existing = db.query(Party).filter(Party.id == party_id).first()
        if not existing:
            party = Party(id=party_id, name=name, short_name=short_name)
            db.add(party)
            count += 1
        else:
            # Update if changed
            updated = False
            if existing.name != name:
                existing.name = name
                updated = True
            if existing.short_name != short_name:
                existing.short_name = short_name
                updated = True
            if updated:
                count += 1

    db.commit()
    return count


def seed_parliaments_as_elections(db: Session) -> int:
    """Seed elections table from parliaments.json.

    Maps parliaments to elections using the exact IDs from the JSON file.
    The 'Election' field is used as the election_type, and the scope
    is derived from the parliament's Shortcut.
    """
    data = load_json_data("parliaments.json")
    count = 0

    for parliament_id_str, info in data.items():
        election_id = int(parliament_id_str)
        shortcut = info.get("Shortcut", "")
        name = info.get("Name", "")
        info.get("Election", "")

        # Determine scope from shortcut
        scope = (
            shortcut.lower().replace(" ", "-").replace("(", "").replace(")", "")
            if shortcut
            else None
        )

        # Determine election type and year
        if "Bundestag" in name or election_id == 0:
            election_type = "Bundestagswahl"
            year = None  # Federal elections span multiple years
            scope = "federal"
        elif "Europäisches" in name:
            election_type = "Europawahl"
            year = None
            scope = "eu"
        else:
            # State elections
            election_type = "Landtagswahl"
            year = None

        existing = db.query(Election).filter(Election.id == election_id).first()
        if not existing:
            election = Election(
                id=election_id, election_type=election_type, year=year, scope=scope, date=None
            )
            db.add(election)
            count += 1
        else:
            # Update if changed
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
    """Seed all reference tables from JSON files.

    Returns a dictionary with counts of inserted/updated records.
    """
    return {
        "institutes": seed_institutes_from_json(db),
        "methods": seed_methods_from_json(db),
        "taskers": seed_taskers_from_json(db),
        "parties": seed_parties_from_json(db),
        "elections": seed_parliaments_as_elections(db),
    }
