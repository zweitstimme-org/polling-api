from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_datetime(
    value: datetime | str,
) -> datetime:  # did this so the time takes in more formats
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


class SourcePartyResult(BaseModel):
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
    survey_type: str | None = None  # optional survey type parameter
    results: list[SourcePartyResult]

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
    results: list[SourcePartyResult]


class ElectionScope(StrEnum):
    BUNDESTAGSWAHL = "Bundestagswahl"
    LANDTAGSWAHL = "Landtagswahl"
    EU_WAHLEN = "Europawahl"


class GermanState(StrEnum):
    BUND = "Bund"  # complete Population
    BY = "BY  | (Bayern)"
    BW = "BW  | (Baden-Württemberg)"
    BE = "BE  | (Berlin)"
    BB = "BB  | (Brandenburg)"
    HB = "HB  | (Bremen)"
    HH = "HH  | (Hamburg)"
    HE = "HE  | (Hessen)"
    MV = "MV  | (Mecklenburg-Vorpommern)"
    NI = "NI  | (Niedersachsen)"
    NW = "NW  | (Nordrhein-Westfalen)"
    RP = "RP  | (Rheinland-Pfalz)"
    SL = "SL  | (Saarland)"
    SN = "SN  | (Sachsen)"
    ST = "ST  | (Sachsen-Anhalt)"
    SH = "SH  | (Schleswig-Holstein)"
    TH = "TH  | (Thüringen)"
    OST = "Ost  | Former east German States"
    WEST = "West  | Former west German States"


class DataSource(StrEnum):
    WAHLRECHT = "Wahlrecht.de"
    DAWUM = "Dawum"


class SurveyMethod(StrEnum):
    ONLINE = "Online"
    TELEFONISCH = "Telefonisch"
    TELEFON_ONLINE = "Telefon & Online"
    PERSOENLICH = "Persönlich"
    UNBEKANNT = "99"


class SurveyType(StrEnum):
    PROJEKTION = "Projektion"
    POLITISCHE_STIMMUNG = "Stimmung"


class Institute(StrEnum):
    INFRATEST = "Infratest Dimap"
    FORSA = "Forsa"
    INSA = "INSA"
    FORSCHUNGSGRUPPE_WAHLEN = "Forschungsgruppe Wahlen"
    ALLENSBACH = "Allensbach"
    CIVEY = "Civey"
    VERIAN = "Verian (Emnid)"
    IPSOS = "Ipsos"
    YOUGOV = "YouGov"
    POLLYTIX = "pollytix"
    GMS = "GMS"
    INSTITUT_WAHLKREISPROGNOSE = "Institut Wahlkreisprognose"
    TREND_RESEARCH_HAMBURG = "Trend Research Hamburg"
    IMF_BERLIN = "IMF Berlin"
    POLICY_MATTERS = "Policy Matters"
    UNIVESITAET_HAMBURG = "Universität Hamburg"
    MENTEFACTUM = "Mentefactum"
    IM_FIELD = "IM Field"
    UNIQMA = "uniQma"
    CONOSCOPE = "Conoscope"
    DIMAP = "DIMAP"


class Tasker(StrEnum):
    ARD = "ARD"
    ARD_MORGENMAGAZIN = "ARD-Morgenmagazin"
    ARD_POLITIKMAGAZIN_KONTRASTE = "ARD-Politikmagazin Kontraste"
    ARD_TAGESTHEMEN = "ARD-Tagesthemen"
    AUGSBURGER_ALLGEMEINE = "Augsburger Allgemeine"
    BAYERISCHER_RUNDFUNK = "Bayerischer Rundfunk"
    BERLINER_ZEITUNG = "Berliner Zeitung"
    BILD = "BILD"
    BILD_AM_SONNTAG = "BILD am Sonntag"
    BILD_B_Z = "BILD / B.Z."
    BILD_WELT = "BILD / WELT"
    BR_POLITIKMAGAZIN_KONTROVERS = "BR-Politikmagazin Kontrovers"
    BUERGER_IN_WUT = "Bürger in Wut"
    B_Z = "B.Z."
    CAMPACT = "Campact"
    CDU_BRANDENBURG = "CDU Brandenburg"
    CDU_BREMEN = "CDU Bremen"
    CDU_NIEDERSACHSEN = "CDU Niedersachsen"
    CDU_SACHSEN = "CDU Sachsen"
    CICERO = "Cicero"
    CSU = "CSU"
    DER_HAUPTSTADTBRIEF = "Der Hauptstadtbrief"
    DER_TAGESSPIEGEL = "Der Tagesspiegel"
    DIE_LINKE_BRANDENBURG = "Die Linke Brandenburg"
    DIE_ZEIT = "DIE ZEIT"
    DIE_ZEIT_KOERBER_STIFTUNG = "DIE ZEIT / Körber-Stiftung"
    DREI_QUELLEN_MEDIENGRUPPE = "Drei Quellen-Mediengruppe"
    EURONEWS = "Euronews"
    FAZ_HITRADIO_FFH = "FAZ / Hitradio FFH"
    FDP_BAYERN = "FDP Bayern"
    FOCUS = "FOCUS"
    FORSA = "Forsa"
    FORUM = "Wochenmagazin Forum"
    GESS_PHONE_FIELD = "GESS Phone & Field"
    FRANKFURTER_ALLGEMEINE_ZEITUNG = "Frankfurter Allgemeine Zeitung"
    FUNKE_MEDIEN_THUERINGEN = "FUNKE Medien Thüringen"
    FUNKE_NRW_REDAKTIONSGESELLSCHAFT = "FUNKE NRW Redaktionsgesellschaft"
    GENERAL_ANZEIGER_BONN = "General-Anzeiger Bonn"
    GMS = "GMS"
    HAMBURGER_ABENDBLATT = "Hamburger Abendblatt"
    HAMBURG_ZWEI = "Hamburg Zwei"
    HESSISCHER_RUNDFUNK = "Hessischer Rundfunk"
    HESSISCHE_NIEDERSAECHSISCHE_ALLGEMEINE = "Hessische Niedersächsische Allgemeine"
    INSTITUT_WAHLKREISPROGNOSE = "Institut Wahlkreisprognose"
    IPSOS = "Ipsos"
    KOELNER_STADT_ANZEIGER_EXPRESS = "Kölner Stadt-Anzeiger / Express"
    KOERBER_STIFTUNG = "Körber-Stiftung"
    LEIPZIGER_VOLKSZEITUNG = "Leipziger Volkszeitung"
    LPB_SACHSEN_ANHALT = "Landeszentrale für politische Bildung Sachsen-Anhalt"
    MAERKISCHE_ALLGEMEINE = "Märkische Allgemeine"
    MAERKISCHE_ALLGEMEINE_MOZ_LR = "Märkische Allgemeine Zeitung (MAZ) / Märkische Oderzeitung (MOZ) / Lausitzer Rundschau (LR)"
    MAERKISCHE_ODERZEITUNG = "Märkische Oderzeitung (MOZ)"
    MDR = "MDR"
    MDR_MITTELDEUTSCHE_ZEITUNG_VOLKSSTIMME = "MDR / Mitteldeutsche Zeitung / Volksstimme"
    NDR = "NDR"
    NDR_OSTSEE_ZEITUNG = "NDR / Ostsee-Zeitung"
    NDR_OSTSEE_ZEITUNG_SCHWERINER_VOLKSZEITUNG = "NDR / Ostsee-Zeitung / Schweriner Volkszeitung"
    NIEDERSAECHSISCHE_TAGESZEITUNGEN = "Niedersächsische Tageszeitungen"
    NIUS = "NIUS"
    NORDKURIER = "Nordkurier"
    NRW_TAGESZEITUNGEN = "NRW-Tageszeitungen"
    OSTHESSEN_NEWS = "Osthessen|News"
    OSTSEE_ZEITUNG = "Ostsee-Zeitung"
    POLLYTIX = "pollytix"
    RADIO_BREMEN = "Radio Bremen"
    RADIO_BREMEN_NORDSEE_ZEITUNG = "Radio Bremen / Nordsee-Zeitung"
    RADIO_HAMBURG = "Radio Hamburg"
    RADIO_HAMBURG_DIE_ZEIT = "Radio Hamburg / Die ZEIT"
    RBB_ABENDSCHAU_RBB_88_8 = "RBB Abendschau / RBB 88.8"
    RBB_BERLINER_MORGENPOST = "RBB / Berliner Morgenpost"
    RBB_BRANDENBURG_AKTUELL = "RBB Brandenburg aktuell"
    RBB_BRANDENBURG_AKTUELL_ANTENNE_BRANDENBURG = "RBB Brandenburg aktuell / Antenne Brandenburg"
    RENEWEU = "renewEU"
    RHEINISCHE_POST = "Rheinische Post"
    RHEINISCHE_POST_GENERAL_ANZEIGER_AACHEN = (
        "Rheinische Post / Bonner General-Anzeiger / Zeitungsverlag Aachen"
    )
    RHEINPFALZ = "Rheinpfalz"
    RND = "RedaktionsNetzwerk Deutschland (RND)"
    RTL_N_TV = "RTL / n-tv"
    SAARLAENDISCHER_RUNDFUNK = "Saarländischer Rundfunk"
    SAECHSISCHE_ZEITUNG = "Sächsische Zeitung"
    SAECHSISCHE_ZEITUNG_FREIE_PRESSE_LVZ = (
        "Sächsische Zeitung / Freie Presse / Leipziger Volkszeitung"
    )
    SAECHSISCHE_ZEITUNG_LEIPZIGER_VOLKSZEITUNG = "Sächsische Zeitung / Leipziger Volkszeitung"
    SAT_1_BAYERN = "SAT.1 Bayern"
    SAT_1_BAYERN_ANTENNE_BAYERN = "SAT.1 Bayern / Antenne Bayern"
    SAT_1_NRW = "SAT.1 NRW"
    SCHWAEBISCHE_ZEITUNG = "Schwäbische Zeitung"
    SCHWERINER_VOLKSZEITUNG = "Schweriner Volkszeitung"
    SEVEN_ONE = "Seven.One"
    SPD_BRANDENBURG = "SPD Brandenburg"
    SPD_BREMEN = "SPD Bremen"
    SPD_NIEDERSACHSEN = "SPD Niedersachsen"
    SPIEGEL_ONLINE = "Spiegel Online"
    SPIEGEL_ONLINE_AUGSBURGER_ALLGEMEINE = "Spiegel Online / Augsburger Allgemeine"
    SPIEGEL_ONLINE_HAZ = "Spiegel Online / Hannoversche Allgemeine Zeitung"
    SPIEGEL_ONLINE_HNA = "Spiegel Online / Hessische Niedersächsische Allgemeine"
    SPIEGEL_ONLINE_RP = "Spiegel Online / RP Online"
    SPIEGEL_ONLINE_TAGESSPIEGEL = "Spiegel Online / Der Tagesspiegel"
    STERN_RTL = "Stern / RTL"
    STERN_RTL_KSTA = "Stern / RTL / Kölner Stadt-Anzeiger"
    SUEDDEUTSCHE_ZEITUNG = "Süddeutsche Zeitung"
    SWR = "SWR"
    SWR_STUTTGARTER_ZEITUNG = "SWR / Stuttgarter Zeitung"
    SWR_ZUR_SACHE_RHEINLAND_PFALZ = "SWR Zur Sache Rheinland-Pfalz"
    THUERINGEN_ALLGEMEINE = "Thüringer Allgemeine"
    T_ONLINE = "t-online"
    UNIVERSITAET_HAMBURG = "Universität Hamburg"
    VERLAG_NUERNBERGER_PRESSE = "Verlag Nürnberger Presse"
    WDR = "WDR"
    WDR_WESTPOL = "WDR-Westpol"
    WESER_KURIER = "Weser-Kurier"
    YOUGOV = "YouGov"
    ZDF_POLITBAROMETER = "ZDF-Politbarometer"


class Party(StrEnum):
    AFD = "Alternative für Deutschland"
    BAYERNPARTEI = "Bayernpartei e.V."
    BD = "Bündnis Deutschland"
    BFTH = "Bürger für Thüringen"
    BSW = "Bündnis Sahra Wagenknecht"
    BUNT_SAAR = "bunt.saar – sozial-ökologische liste"
    BVB_FW = "Brandenburger Vereinigte Bürgerbewegungen/Freie Wähler"
    CDU = "Christlich Demokratische Union"
    CDU_CSU = "Union | Christlich Demokratische Union & Christlich-Soziale Union"
    CSU = "Christlich-Soziale Union"
    DIE_PARTEI = "Partei für Arbeit, Rechtsstaat, Tierschutz, Elitenförderung und basisdemokratische Initiative"
    FAMILIE = "Familienpartei Deutschlands"
    FDP = "Freie Demokratische Partei"
    FREIE_WAEHLER = "Freie Wähler"
    GRUENE = "Bündnis 90/Die Grünen"
    LINKE = "Die Linke"
    NPD = "Nationaldemokratische Partei Deutschlands"
    OEDP = "Ökologisch-Demokratische Partei"
    PIRATEN = "Piratenpartei"
    PLUS_BRANDENBURG = "Plus Brandenburg (Listenvereinigung aus Piratenpartei, ÖDP und Volt)"
    SONSTIGE = "sonstige Parteien"
    SPD = "Sozialdemokratische Partei Deutschlands"
    SSW = "Südschleswigscher Wählerverband"
    TIERSCHUTZPARTEI = "Partei Mensch Umwelt Tierschutz"
    VOLT = "Volt Deutschland"
    WERTEUNION = "WerteUnion"


class PartyResult(BaseModel):
    party: Party
    value: float
