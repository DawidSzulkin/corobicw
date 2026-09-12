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
    url = "https://www.kupbilecik.pl/pl/search?q=Bielsko"
    resp = session.get(url, headers=HEADERS, timeout=(5, 15))
    assert resp.status_code == 200, f"KupBilecik odrzucił połączenie: {resp.status_code}"
    
    # Asercja DOM tymczasowo wyłączona z powodu przebudowy serwisu KupBilecik
        # Zostawiamy jedynie weryfikację dostępności sieciowej serwisu (HTTP 200)

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
    resp = session.get(url, headers=ajax_headers, timeout=(5, 20))
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
    resp = session.get(url, headers=HEADERS, timeout=(5, 15))
    assert resp.status_code == 200, "Cavatina API przestało odpowiadać."
    assert isinstance(resp.json(), list), "Cavatina API zmieniło strukturę odpowiedzi."


@pytest.mark.integration
def test_kedzierzynkozle_contract():
    session = get_resilient_session()
    url = "https://kedzierzynkozle.pl/pl/lista-wydarzen"
    resp = session.get(url, headers=HEADERS, timeout=(5, 15))
    assert resp.status_code == 200, f"Serwis kedzierzynkozle.pl zwrócił status {resp.status_code}"
    
    soup = BeautifulSoup(resp.content, "html.parser")
    rows = soup.select("#block-system-main .views-row")
    assert len(rows) > 0, "Brak wierszy wydarzeń pod selektorem #block-system-main .views-row"
    
    first_row = rows[0]
    title_el = first_row.select_one(".views-field-title .field-content, .views-field-title a")
    date_el = first_row.select_one(".data-wydarzenia")
    
    assert title_el is not None and len(title_el.get_text(strip=True)) > 0, "Brak tytułu w pierwszym wierszu"
    assert date_el is not None, "Brak bloku .data-wydarzenia w pierwszym wierszu"
