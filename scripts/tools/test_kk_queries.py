import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
queries = ["Kędzierzyn-Koźle", "Kedzierzyn-Kozle", "Kędzierzyn", "Koźle"]

print("[TEST FRAZ WYSZUKIWARKI KUPBILECIK]")
for q in queries:
    url = f"https://www.kupbilecik.pl/szukaj/?q={quote_plus(q)}"
    resp = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    events = set()
    for a in soup.select("a[href*='/imprezy/']"):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if title and title.lower() not in ["informacje", "kup bilet", "bilety"]:
            events.add((title, href))
            
    print(f"\nFraza: '{q}' -> Unikalnych wydarzeń: {len(events)}")
    for t, h in events:
        print(f"  - {t} ({h})")

