import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.database import Base
from pollingapi.database_seed import party_external_ids, seed_parties_from_datamodel
from pollingapi.models import Party


def test_seed_parties_sets_external_ids(tmp_path, monkeypatch):
    mapping_path = tmp_path / "party_external_ids.json"
    mapping_path.write_text(
        json.dumps({"SPD": {"partyfacts": "123", "wikidata": "Q49766"}, "CDU_CSU": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("pollingapi.database_seed.PARTY_EXTERNAL_IDS_PATH", mapping_path)
    party_external_ids.cache_clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    seed_parties_from_datamodel(session)

    assert session.get(Party, "SPD").external_ids == {
        "partyfacts": "123",
        "wikidata": "Q49766",
    }
    assert session.get(Party, "CDU_CSU").external_ids is None
