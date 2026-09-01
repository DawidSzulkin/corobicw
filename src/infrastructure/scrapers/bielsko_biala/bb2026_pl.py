import html
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Set
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KNOWN_VENUES_LOOKUP = [
    ("galeria bielska", "Galeria Bielska BWA", "ul. 3 Maja 11, Bielsko-Biała"),
    ("bwa", "Galeria Bielska BWA", "ul. 3 Maja 11, Bielsko-Biała"),
    ("willa sixta", "Willa Sixta (Galeria Bielska BWA)", "ul. Mickiewicza 24, Bielsko-Biała"),
    ("teatr polski", "Teatr Polski w Bielsku-Białej", "ul. 1 Maja 1, Bielsko-Biała"),
    ("banialuk", "Teatr Lalek Banialuka", "ul. Mickiewicza 20, Bielsko-Biała"),
    ("cavatina", "Cavatina Hall", "ul. Dworkowa 2, Bielsko-Biała"),
    ("bck", "Bielskie Centrum Kultury im. M. Koterbskiej", "ul. Słowackiego 27, Bielsko-Biała"),
    ("bielskie centrum kultury", "Bielskie Centrum Kultury im. M. Koterbskiej", "ul. Słowackiego 27, Bielsko-Biała"),
    ("książnic", "Książnica Beskidzka", "ul. Słowackiego 17a, Bielsko-Biała"),
    ("zamek sułkowskich", "Zamek Książąt Sułkowskich - Muzeum Historyczne", "ul. Wzgórze 16, Bielsko-Biała"),
    ("muzeum historyczn", "Zamek Książąt Sułkowskich - Muzeum Historyczne", "ul. Wzgórze 16, Bielsko-Biała"),
    ("starówce", "Rynek Starego Miasta", "Rynek, Bielsko-Biała"),
    ("rynek", "Rynek Starego Miasta", "Rynek, Bielsko-Biała"),
    ("plac wojska polskiego", "Plac Wojska Polskiego", "Plac Wojska Polskiego, Bielsko-Biała"),
    ("plac chrobrego", "Plac Bolesława Chrobrego", "Plac Bolesława Chrobrego, Bielsko-Biała"),
    ("park słowackiego", "Park im. Juliusza Słowackiego", "ul. Słowackiego, Bielsko-Biała"),
    ("dom kultury", "Dom Kultury im. Wiktorii Kubisz", "ul. Słowackiego 17, Bielsko-Biała"),
]

class Bb2026PlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="bb2026_pl",
            base_url="https://bb2026.pl"
        )
        self.api_url = f"{self.base_url}/wp-json/tribe/events/v1/events"
        self.seen_signatures: Set[str] = set()

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie wydarzeń z kalendarium BB2026...")
        page = 1
        per_page = 50

        while True:
            params = {
                "per_page": per_page,
                "page": page,
                "status": "publish"
            }

            try:
                resp = self.session.get(
                    self.api_url,
                    params=params,
                    verify=False,
                    timeout=(5.0, 15.0)
                )

                if resp.status_code != 200:
                    break

                data = resp.json()
                raw_items = data.get("events", [])
                if not raw_items:
                    break

                for item in raw_items:
                    raw_title = item.get("title", "")
                    title = self._clean_text(raw_title)
                    if not title:
                        continue

                    start_str = item.get("start_date", "")
                    end_str = item.get("end_date", "")

                    date_start = start_str[:10] if len(start_str) >= 10 else ""
                    date_end = end_str[:10] if len(end_str) >= 10 else date_start

                    if not date_start or (date_end and date_end < today_iso):
                        continue

                    all_day = item.get("all_day", False)
                    time_start = "Całodniowe" if all_day else (start_str[11:16] if len(start_str) >= 16 else "18:00")

                    sig = f"{date_start}_{time_start}_{title.lower()}"
                    if sig in self.seen_signatures:
                        continue
                    self.seen_signatures.add(sig)

                    # Wyciągnięcie opisu
                    desc_raw = item.get("description", "")
                    description = self._clean_text(desc_raw)
                    if not description:
                        description = f"Wydarzenie w ramach Polskiej Stolicy Kultury 2026: {title}."

                    # Inteligentne ustalanie miejsca
                    venue_data = item.get("venue")
                    venue_name = ""
                    address = "Bielsko-Biała"

                    if isinstance(venue_data, dict) and venue_data.get("venue"):
                        v_name = self._clean_text(venue_data.get("venue"))
                        if v_name.lower() not in ["bielsko-biała", "bielsko biala", "bielsko"]:
                            venue_name = v_name
                            v_addr = venue_data.get("address")
                            v_city = venue_data.get("city") or "Bielsko-Biała"
                            address = f"{v_addr}, {v_city}".strip(" ,") if v_addr else v_city

                    # Jeśli brak miejsca w obiekcie API, przeszukaj tytuł i treść
                    if not venue_name:
                        search_corpus = f"{title} {description}".lower()
                        for key, canonical_v, canonical_addr in KNOWN_VENUES_LOOKUP:
                            if key in search_corpus:
                                venue_name = canonical_v
                                address = canonical_addr
                                break

                    if not venue_name:
                        venue_name = "Przestrzeń Miejska Bielsko-Biała"
                        address = "Bielsko-Biała"

                    # Organizator
                    organizer_data = item.get("organizer", [])
                    organizer = "Bielsko-Biała 2026"
                    if isinstance(organizer_data, list) and organizer_data:
                        org_obj = organizer_data[0]
                        if isinstance(org_obj, dict) and org_obj.get("organizer"):
                            organizer = self._clean_text(org_obj.get("organizer"))
                    elif isinstance(organizer_data, dict) and organizer_data.get("organizer"):
                        organizer = self._clean_text(organizer_data.get("organizer"))

                    # Kategorie i Ceny
                    categories = [c.get("name", "") for c in item.get("categories", []) if isinstance(c, dict) and c.get("name")]
                    cost = item.get("cost", "").strip()

                    if any("bezpłat" in c.lower() for c in categories) or cost.lower() in ["0", "0 zł", "free", "bezpłatne"]:
                        price_info = "Wstęp bezpłatny"
                    elif cost:
                        price_info = cost
                    else:
                        price_info = "Wstęp wolny / Sprawdź szczegóły"

                    # Plakat
                    image_obj = item.get("image")
                    image_url = ""
                    if isinstance(image_obj, dict):
                        image_url = image_obj.get("url", "")
                    elif isinstance(image_obj, str):
                        image_url = image_obj

                    processed_img = ""
                    if image_url:
                        thumb = self.save_thumbnail(image_url, title, prefix="bb2026")
                        processed_img = thumb or image_url

                    event_url = item.get("url") or f"{self.base_url}/kalendarium/"

                    events.append({
                        "title": title,
                        "date_start": date_start,
                        "date_end": date_end,
                        "time_start": time_start,
                        "venue": venue_name,
                        "address": address,
                        "price_range": price_info,
                        "description": description,
                        "image_url": processed_img,
                        "source_url": event_url,
                        "source": self.source_name,
                        "organizer": organizer,
                        "category": "Kultura i Sztuka"
                    })

                total_pages = data.get("total_pages", 1)
                if page >= total_pages:
                    break
                page += 1

            except Exception as e:
                print(f"[{self.source_name}] Błąd podczas pobierania strony {page}: {e}")
                break

        print(f"[{self.source_name}] Łącznie sparsowano: {len(events)} aktywnych wydarzeń.")
        return events
