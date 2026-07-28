from pollingapi.scraper.runner import ScraperRunner
from pollingapi.scraper.workers.sites_eu.eu_fed import EuFedCurrentScraper
from pollingapi.scraper.workers.sites_eu.eu_state import EuStateCurrentScraper

HTML = """
<table class="wilko"><thead><tr>
<th>Datum</th><th>&nbsp;</th><th>Institut</th><th>Auftrag-<br>geber</th>
<th>Befragte<br>Zeitraum</th><th>&nbsp;</th><th>CDU</th><th>CSU</th><th>SPD</th>
<th>GRÜNE</th><th>FDP</th><th>LINKE</th><th>Sonstige</th>
</tr></thead><tbody>
<tr><td colspan="5">Europawahl am 09.06.2024</td><td>&nbsp;</td><td>23,7 %</td></tr>
<tr><td>07.06.2024</td><td>&nbsp;</td><td>Ipsos</td><td>Ipsos</td>
<td>TOM • 2.000<br>29.05.–05.06.</td><td>&nbsp;</td><td colspan="2">30 %</td>
<td>15 %</td><td>15 %</td><td>5 %</td><td>3 %</td><td>8 %</td></tr>
</tbody></table>
<table class="wilko"><thead><tr>
<th>Datum</th><th>&nbsp;</th><th>Institut</th><th>Auftrag-<br>geber</th>
<th>Befragte<br>Zeitraum</th><th>&nbsp;</th><th>CDU</th><th>CSU</th><th>SPD</th>
<th>GRÜNE</th><th>FDP</th><th>LINKE</th><th>Sonstige</th>
</tr></thead><tbody></tbody></table>
<table class="wilko"><thead><tr>
<th>&nbsp;</th><th>&nbsp;</th><th>Institut<br>(Datum)</th><th>Auftrag-<br>geber</th>
<th>Befragte<br>Zeitraum</th><th>&nbsp;</th><th>CDU/CSU</th><th>SPD</th><th>GRÜNE</th>
<th>FDP</th><th>LINKE</th><th>AfD</th><th>Sonstige</th>
</tr></thead><tbody>
<tr><th class="li" id="bw" rowspan="1">Baden-Württemberg</th><td>&nbsp;</td>
<td>INSA<br><span>(18.05.19)</span></td><td>BILD</td>
<td title="Online-Panel">O • 505<br>10.05.–13.05.</td><td>&nbsp;</td><td>28 %</td><td>12 %</td>
<td>20 %</td><td>9 %</td><td>5 %</td><td>12 %</td><td>FW 4 %<br>Sonst. 10 %</td></tr>
</tbody></table>
"""


def test_eu_federal_scraper_parses_poll_rows_only():
    polls = EuFedCurrentScraper(db=None).parse(HTML)

    assert len(polls) == 1
    assert polls[0].datum == "07.06.2024"
    assert polls[0].institut == "Ipsos"
    assert [(result.name, result.value) for result in polls[0].results[:2]] == [
        ("CDU/CSU", "30 %"),
        ("SPD", "15 %"),
    ]


def test_eu_state_scraper_parses_state_rows():
    polls = EuStateCurrentScraper(db=None).parse(HTML)

    assert len(polls) == 1
    assert polls[0].datum == "18.05.19"
    assert polls[0].state.startswith("BW")
    assert polls[0].institut == "INSA"
    assert polls[0].befragte == "O • 505 Online-Panel"
    assert polls[0].zeitraum == "10.05.–13.05."
    assert polls[0].results[-1].name == "Sonstige"


def test_runner_discovers_eu_workers():
    names = ScraperRunner(db=None).list_workers(include_dawum=False)

    assert "eu_fed" in names
    assert "eu_state" in names
