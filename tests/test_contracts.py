import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def get_resilient_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

@pytest.mark.integration
def test_kupbilecik_contract():
    session = get_resilient_session()
    url = "https://www.kupbilecik.pl/szukaj/?q=Bielsko"
    resp = session.get(url, headers=HEADERS, verify=False, timeout=(5, 15))
    assert resp.status_code == 200, f"KupBilecik odrzucił połączenie: {resp.status_code}"
    
    soup = BeautifulSoup(resp.content, "html.parser")
    cards = soup.select(".wyd-szukaj-table, .row-cell")
    assert len(cards) > 0, "Zmiana struktury HTML KupBilecika: Brak elementów z klasą .wyd-szukaj-table"

@pytest.mark.integration
def test_banialuka_contract():
    session = get_resilient_session()
    url = "https://banialuka.pl/ajax/get-simple-repertoire"
    ajax_headers = {
        **HEADERS,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://banialuka.pl/repertuar",
        "Accept": "application/json, text/plain, */*"
    }
    resp = session.get(url, headers=ajax_headers, verify=False, timeout=(5, 20))
    assert resp.status_code == 200, f"Banialuka AJAX odrzuciła połączenie: {resp.status_code}"
    
    data = resp.json()
    assert "html" in data, "Brak klucza html w odpowiedzi AJAX Banialuki"
    
    soup = BeautifulSoup(data["html"], "html.parser")
    articles = soup.find_all("article", class_="small-event-row")
    assert len(articles) > 0, "Zmiana struktury repertuaru Banialuki: brak elementów .small-event-row"

@pytest.mark.integration
def test_cavatina_contract():
    session = get_resilient_session()
    url = "https://cavatinahall.pl/wp-json/wp/v2/events?per_page=1"
    resp = session.get(url, headers=HEADERS, verify=False, timeout=(5, 15))
    assert resp.status_code == 200, "Cavatina API przestało odpowiadać."
    assert isinstance(resp.json(), list), "Cavatina API zmieniło strukturę odpowiedzi."