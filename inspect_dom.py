import urllib3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://www.mok.kedzierzyn-kozle.com.pl"
headers = {"User-Agent": "Mozilla/5.0"}

resp = requests.get(base_url, headers=headers, verify=False)
soup = BeautifulSoup(resp.text, "html.parser")

keywords = ["zapowiedzi", "wydarzen", "festiwal", "kino", "repertuar", "koncert", "spektakl"]
target_urls = set()

for a in soup.find_all("a", href=True):
    href = a["href"].strip()
    text = a.get_text(strip=True).lower()
    if any(kw in text or kw in href.lower() for kw in keywords):
        full = urljoin(base_url, href)
        if "mok.kedzierzyn-kozle.com.pl" in full:
            target_urls.add((a.get_text(strip=True), full))

print(f"=== WYKRYTE PODSTRONY ({len(target_urls)}) ===")
for name, url in target_urls:
    print(f"\n[SEKCJA]: {name} -> {url}")
    try:
        sub_resp = requests.get(url, headers=headers, timeout=8, verify=False)
        sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
        
        # Usuwamy nawigację, żeby zobaczyć tylko ciało podstrony
        for tag in sub_soup.select("header, footer, nav, .menu"):
            tag.decompose()

        print("  Znalezione linki w głównej treści:")
        links = sub_soup.find_all("a", href=True)
        count = 0
        for l in links:
            txt = l.get_text(strip=True)
            hr = l["href"]
            parent_class = l.parent.get("class", [])
            if len(txt) > 4 and not hr.startswith(("#", "javascript:")):
                print(f"    - <a href='{hr}'> ({txt}) | Rodzic: <{l.parent.name} class='{parent_class}'>")
                count += 1
                if count >= 6:
                    break
        if count == 0:
            print("    [BRAK LINKÓW] Sprawdźmy nagłówki tekstowe na tej podstronie:")
            for h in sub_soup.find_all(["h1", "h2", "h3", "h4", "p"])[:4]:
                print(f"    - <{h.name}>: {h.get_text(strip=True)[:80]}")
    except Exception as e:
        print(f"  Błąd: {e}")