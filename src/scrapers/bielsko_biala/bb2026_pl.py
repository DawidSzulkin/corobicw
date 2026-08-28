import html
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Set
import urllib3

# Zapewnia widocznosc katalogu glownego projektu z poziomu src/scrapers/bielsko_biala/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
                    if all_day:
                        time_start = "Całodniowe"
                    else:
                        time_start = start_str[11:16] if len(start_str) >= 16 else "Według harmonogramu"

                    sig = f"{date_start}_{time_start}_{title.lower()}"
                    if sig in self.seen_signatures:
                        continue
                    self.seen_signatures.add(sig)

                    # Miejsce / Venue
                    venue_data = item.get("venue")
                    venue_name = "Bielsko-Biała"
                    address = "Bielsko-Biała"

                    if isinstance(venue_data, dict):
                        v_name = venue_data.get("venue")
                        if v_name:
                            venue_name = self._clean_text(v_name)
                        v_addr = venue_data.get("address")
                        v_city = venue_data.get("city") or "Bielsko-Biała"
                        if v_addr:
                            address = f"{v_addr}, {v_city}".strip(" ,")
                        else:
                            address = v_city

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
                    categories = [
                        c.get("name", "") for c in item.get("categories", [])
                        if isinstance(c, dict) and c.get("name")
                    ]
                    cost = item.get("cost", "").strip()

                    if any("bezpłat" in c.lower() for c in categories) or cost.lower() in ["0", "0 zł", "free", "bezpłatne"]:
                        price_info = "Wstęp bezpłatny"
                    elif cost:
                        price_info = cost
                    else:
                        price_info = "Sprawdź szczegóły / Bilety"

                    # Opis
                    desc_raw = item.get("description", "")
                    description = self._clean_text(desc_raw)
                    if not description:
                        description = f"Wydarzenie w ramach Polskiej Stolicy Kultury 2026: {title}."

                    # Grafika / Plakat
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
                        "organizer": organizer
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


if __name__ == "__main__":
    scraper = Bb2026PlScraper()
    results = scraper.fetch_events()
    print(f"\n[OK] Sukces. Zwrócono {len(results)} pozycji.")
    if results:
        print("Przykładowe wydarzenie:", results[0])