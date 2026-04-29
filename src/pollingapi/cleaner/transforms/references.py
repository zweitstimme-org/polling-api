"""Resolve raw reference labels into canonical domain enum members."""

import re
from collections.abc import Iterable
from enum import StrEnum

from pollingapi.scraper.datamodel import GermanState, Institute, SurveyMethod


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def _simplify(value: str) -> str:
    return re.sub(r"[^\w\s]", "", _normalize(value))


def _lookup_enum(raw_value: str, members: Iterable[StrEnum]) -> StrEnum | None:
    normalized = _normalize(raw_value)
    simplified = _simplify(raw_value)

    for member in members:
        if normalized in {_normalize(member.name), _normalize(member.value)}:
            return member
        if simplified == _simplify(member.value):
            return member
    return None


INSTITUTE_ALIASES: dict[str, Institute] = {
    "emnid": Institute.VERIAN,
    "tns emnid": Institute.VERIAN,
    "verian emnid": Institute.VERIAN,
    "infratest": Institute.INFRATEST,
    "tns infratest": Institute.INFRATEST,
    "forschungsgruppe wahlen": Institute.FORSCHUNGSGRUPPE_WAHLEN,
    "forschungsgruppewahlen": Institute.FORSCHUNGSGRUPPE_WAHLEN,
    "fg wahlen": Institute.FORSCHUNGSGRUPPE_WAHLEN,
    "ipos": Institute.IPSOS,
}

METHOD_ALIASES: dict[str, SurveyMethod] = {
    "0": SurveyMethod.UNBEKANNT,
    "99": SurveyMethod.UNBEKANNT,
    "cati": SurveyMethod.TELEFONISCH,
    "telefon": SurveyMethod.TELEFONISCH,
    "telefonisch": SurveyMethod.TELEFONISCH,
    "online": SurveyMethod.ONLINE,
    "cawi": SurveyMethod.ONLINE,
    "panel": SurveyMethod.ONLINE,
    "telefon online": SurveyMethod.TELEFON_ONLINE,
    "telefon & online": SurveyMethod.TELEFON_ONLINE,
    "telefon und online": SurveyMethod.TELEFON_ONLINE,
    "tom": SurveyMethod.TELEFON_ONLINE,
    "to": SurveyMethod.TELEFON_ONLINE,
    "mixed": SurveyMethod.TELEFON_ONLINE,
    "persoenlich": SurveyMethod.PERSOENLICH,
    "persönlich": SurveyMethod.PERSOENLICH,
    "face to face": SurveyMethod.PERSOENLICH,
    "f2f": SurveyMethod.PERSOENLICH,
}

STATE_ALIASES: dict[str, GermanState] = {
    "bund": GermanState.BUND,
    "bundestag": GermanState.BUND,
    "bundestagswahl": GermanState.BUND,
    "federal": GermanState.BUND,
    "deutschland": GermanState.BUND,
    "eu": GermanState.BUND,
    "europawahl": GermanState.BUND,
    "bw": GermanState.BW,
    "baden-württemberg": GermanState.BW,
    "baden-wuerttemberg": GermanState.BW,
    "by": GermanState.BY,
    "bayern": GermanState.BY,
    "bavaria": GermanState.BY,
    "be": GermanState.BE,
    "berlin": GermanState.BE,
    "bb": GermanState.BB,
    "brandenburg": GermanState.BB,
    "hb": GermanState.HB,
    "bremen": GermanState.HB,
    "hh": GermanState.HH,
    "hamburg": GermanState.HH,
    "he": GermanState.HE,
    "hessen": GermanState.HE,
    "mv": GermanState.MV,
    "mecklenburg-vorpommern": GermanState.MV,
    "ni": GermanState.NI,
    "niedersachsen": GermanState.NI,
    "nw": GermanState.NW,
    "nrw": GermanState.NW,
    "nordrhein-westfalen": GermanState.NW,
    "rp": GermanState.RP,
    "rheinland-pfalz": GermanState.RP,
    "sl": GermanState.SL,
    "saarland": GermanState.SL,
    "sn": GermanState.SN,
    "sachsen": GermanState.SN,
    "st": GermanState.ST,
    "sachsen-anhalt": GermanState.ST,
    "sh": GermanState.SH,
    "schleswig-holstein": GermanState.SH,
    "th": GermanState.TH,
    "thüringen": GermanState.TH,
    "thueringen": GermanState.TH,
    "ost": GermanState.OST,
    "west": GermanState.WEST,
}


def resolve_institute(raw_value: str | None) -> Institute:
    """Resolve a raw institute label to the canonical institute enum."""
    if not raw_value:
        return Institute.UNKNOWN

    key = _normalize(raw_value)
    if key in INSTITUTE_ALIASES:
        return INSTITUTE_ALIASES[key]

    simplified = _simplify(raw_value)
    if simplified in INSTITUTE_ALIASES:
        return INSTITUTE_ALIASES[simplified]

    direct = _lookup_enum(raw_value, Institute)
    if isinstance(direct, Institute):
        return direct

    for alias, institute in INSTITUTE_ALIASES.items():
        if alias in key or key in alias:
            return institute

    return Institute.UNKNOWN


def resolve_method(raw_value: str | None) -> SurveyMethod:
    """Resolve a raw method label to the canonical survey method enum."""
    if not raw_value:
        return SurveyMethod.UNBEKANNT

    key = _normalize(raw_value)
    if key in METHOD_ALIASES:
        return METHOD_ALIASES[key]

    direct = _lookup_enum(raw_value, SurveyMethod)
    if isinstance(direct, SurveyMethod):
        return direct

    if "telefon" in key and "online" in key:
        return SurveyMethod.TELEFON_ONLINE
    if "telefon" in key:
        return SurveyMethod.TELEFONISCH
    if "online" in key:
        return SurveyMethod.ONLINE
    if "persönlich" in key or "persoenlich" in key:
        return SurveyMethod.PERSOENLICH

    return SurveyMethod.UNBEKANNT


def resolve_state(raw_value: str | None) -> GermanState:
    """Resolve raw scope/state text to the canonical state enum."""
    if not raw_value:
        return GermanState.BUND

    key = _normalize(raw_value)
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]

    simplified = _simplify(raw_value)
    if simplified in STATE_ALIASES:
        return STATE_ALIASES[simplified]

    direct = _lookup_enum(raw_value, GermanState)
    if isinstance(direct, GermanState):
        return direct

    return GermanState.BUND


def normalized_scope(raw_value: str | None) -> str:
    """Return the canonical lower-case scope code used by cleaned polls."""
    state = resolve_state(raw_value)
    if state is GermanState.BUND:
        return "federal"
    if state is GermanState.NW:
        return "nrw"
    return state.name.lower()
