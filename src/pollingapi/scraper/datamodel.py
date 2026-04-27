from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_datetime(
    value: datetime | str,
) -> datetime:  # did this so the time takes in more formats
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


class PartyResult(BaseModel):
    name: str
    value: str


class BundElectionPoll(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    scraped_at: datetime = Field(default_factory=datetime.now)  # at what time was the poll scraped?
    data_source: str  # from where is the poll?
    worker: str  # the worker script identifier
    scope: str  # what population was polled?
    state: str  # what is the actual state that is polled?
    institut: str  # what institute conducted the poll?
    auftraggeber: str | None = None  # who gave the job for the poll?
    datum: str  # what is the publish date of the poll?
    befragte: str  # this includes the amount of the people polled as well as mehtod and timeframe of people polled
    zeitraum: str  # timeframe of the poll
    results: list[PartyResult]

    @field_validator("scraped_at", mode="before")
    @classmethod
    def _coerce_scraped_at(cls, value: datetime | str) -> datetime:
        return _coerce_datetime(value)


class LandElectionPoll(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    scraped_at: datetime = Field(default_factory=datetime.now)  # at what time was the poll scraped?
    data_source: str  # from where is the poll?
    worker: str  # the worker script identifier
    scope: str  # what population was polled?
    state: str  # what is the actual state that is polled?
    institut: str  # what institute conducted the poll?
    auftraggeber: str | None = None  # who gave the job for the poll?
    datum: str  # what is the publish date of the poll?
    befragte: str  # this includes the amount of the people polled as well as mehtod and timeframe of people polled
    zeitraum: str  # timeframe of the poll
    results: list[PartyResult]


class ElectionScope(StrEnum):
    BUNDESTAGSWAHL = "Bundestagswahl"
    LANDTAGSWAHL = "Landtagswahl"
    EU_WAHLEN = "Europawahl"


class GermanState(StrEnum):
    BUND = "Bund"  # complete Population
    BY = "BY"  # (Bayern)
    BW = "BW"  # (Baden-Württemberg)
    BE = "BE"  # (Berlin)
    BB = "BB"  # (Brandenburg)
    HB = "HB"  # (Bremen)
    HH = "HH"  # (Hamburg)
    HE = "HE"  # (Hessen)
    MV = "MV"  # (Mecklenburg-Vorpommern)
    NI = "NI"  # (Niedersachsen)
    NRW = "NRW"  # (Nordrhein-Westfalen)
    RP = "RP"  # (Rheinland-Pfalz)
    SL = "SL"  # (Saarland)
    SN = "SN"  # (Sachsen)
    ST = "ST"  # (Sachsen-Anhalt)
    SH = "SH"  # (Schleswig-Holstein)
    TH = "TH"  # (Thüringen)
    OST = "Ost"  # Former east German States
    WEST = "West"  # Former west German States


class DataSource(StrEnum):
    WAHLRECHT = "Wahlrecht.de"
    DAWUM = "Dawum"


class SurveyMethod(StrEnum):
    ONLINE = "Online"
    TELEFONISCH = "Telefonisch"
    TELEFON_ONLINE = "Telefon & Online"
    PERSOENLICH = "Persönlich"
    UNBEKANNT = "99"
