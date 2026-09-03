import json
import logging
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

OUTPUT_RAW = Path("data/raw/kedzierzyn_kozle_latest.json")
BASE_URL = "https://kedzierzynkozle.pl"
CALENDAR_URL = "https://kedzierzynkozle.pl/pl/wydarzenia"

MONTHS_MAP = {
    "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
    "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
    "września": "09", "października": "10", "listopada": "11", "grudnia": "12"
}

def parse_polish_date(text: str) -> str:
    """Parsuje daty w formatach '28 sierpnia 2026' lub '2026-08-28'."""
    text = text.lower().strip()
    iso_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"

    for pl_month, m_num in MONTHS_MAP.items():
        if pl_month in text:
            day_match = re.search(r"(\d{1,2})", text)
            year_match = re.search(r"(\d{4})", text)
            year = year_match.group(1) if year_match else str(datetime.now().year)
            day = day_match.group(1).zfill(2) if day_match else "01"
            return f"{year}-{m_num}-{day}"

    return datetime.now().strftime("%Y-%m-%d")

def fetch_events() -> list:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    events = []

    try:
        req = urllib.request.Request(CALENDAR_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
        
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all(["article", "div"], class_=re.compile(r"(event|wydarzen|item)"))

        for item in items:
            title_tag = item.find(["h2", "h3", "a"], class_=re.compile(r"title")) or item.find(["h2", "h3"])
            if not title_tag:
                continue
            
            title = title_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            link_tag = item.find("a", href=True)
            event_url = link_tag["href"] if link_tag else CALENDAR_URL
            if event_url.startswith("/"):
                event_url = f"{BASE_URL}{event_url}"

            date_tag = item.find(class_=re.compile(r"(date|czas|termin)"))
            date_raw = date_tag.get_text(strip=True) if date_tag else ""
            date_parsed = parse_polish_date(date_raw)

            desc_tag = item.find(["p", "div"], class_=re.compile(r"(desc|lead|tresc)"))
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            events.append({
                "title": title,
                "date": date_parsed,
                "url": event_url,
                "description": description,
                "source": "Urząd Miasta Kędzierzyn-Koźle"
            })
    except Exception as e:
        logging.warning("Błąd bezpośredniego pobierania z UM (%s). Używam fallbacku cyklicznych.", e)

    # Zapewnienie stałych nadchodzących cykli (np. sobotnie Parkruny)
    today = datetime.now()
    for offset_days in [2, 9, 16, 23]:
        d = today.fromordinal(today.toordinal() + offset_days)
        events.append({
            "title": "parkrun Kędzierzyn-Koźle",
            "date": d.strftime("%Y-%m-%d"),
            "url": "https://www.parkrun.pl/kedzierzynkozle/",
            "description": "Cotygodniowy bezpłatny bieg, trucht lub marsz na dystansie 5 km z pomiarem czasu.",
            "source": "parkrun Polska"
        })

    # Deduplikacja po tytule i dacie
    unique = []
    seen = set()
    for ev in events:
        key = (ev["title"].lower(), ev["date"])
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    return unique

if __name__ == "__main__":
    events_data = fetch_events()
    OUTPUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_RAW, "w", encoding="utf-8") as f:
        json.dump(events_data, f, ensure_ascii=False, indent=2)
    logging.info("Zapisano %d wydarzeń do %s", len(events_data), OUTPUT_RAW)

