from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GaleriaBielskaPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="galeriabielska_pl",
            base_url="https://galeriabielska.pl"
        )
        self.calendar_url = f"{self.base_url}/kalendarium/"
        self.seen_signatures: Set[str] = set()

    def _parse_date(self, text: str, current_year: int) -> str:
        """Wyciąga datę początkową wydarzenia w formacie YYYY-MM-DD."""
        # Szuka wzorca DD.MM.YYYY lub DD.MM
        match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", text)
        if not match:
            return ""

        day, month, year = match.groups()
        y = int(year) if year else current_year
        m = int(month)
        d = int(day)

        try:
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            return ""

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        now = datetime.now()
        today_iso = now.strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie kalendarium Galerii Bielskiej BWA...")

        try:
            resp = self.session.get(self.calendar_url, timeout=(2.0, 6.0), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd pobierania kalendarium: HTTP {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("ul.eventlist a.event")

            for a in items:
                # Pomiń archiwalne oznaczone klasą .-past
                classes = a.get("class", [])
                if "-past" in classes:
                    continue

                event_url = urljoin(self.base_url, a.get("href", ""))
                if not event_url or event_url == self.calendar_url:
                    continue

                txt_container = a.select_one(".event_txt")
                if not txt_container:
                    continue

                full_txt = txt_container.get_text(" ", strip=True)

                # Wyciągnięcie daty
                date_val = self._parse_date(full_txt, current_year=now.year)
                if not date_val or date_val < today_iso:
                    # Sprawdzenie czy to trwająca wystawa z zakresem 'do DD.MM'
                    range_match = re.search(r"do\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", full_txt)
                    if range_match:
                        end_d, end_m, end_y = range_match.groups()
                        end_year = int(end_y) if end_y else now.year
                        end_iso = f"{end_year:04d}-{int(end_m):02d}-{int(end_d):02d}"
                        if end_iso >= today_iso:
                            date_val = today_iso  # Trwająca ekspozycja
                    if not date_val or date_val < today_iso:
                        continue

                # Kategoria i Tytuł
                cat_el = a.select_one(".event_pix")
                category = cat_el.get_text(strip=True) if cat_el else "Wystawa"

                title_el = a.select_one(".event_title, .event_titlepart")
                if title_el:
                    title = title_el.get_text(" ", strip=True)
                else:
                    # Oczyszczenie tekstu z daty
                    clean_title = re.sub(r"\d{1,2}\.\d{1,2}(?:\.\d{4})?.*", "", full_txt).strip()
                    title = clean_title if clean_title else full_txt[:60]

                title = re.sub(r"\s+", " ", title).strip()

                sig = f"{date_val}_{title.lower()}"
                if sig in self.seen_signatures:
                    continue
                self.seen_signatures.add(sig)

                # Grafika
                img_el = a.select_one("img")
                remote_img = ""
                if img_el:
                    remote_img = img_el.get("src") or img_el.get("data-src") or ""
                    if remote_img:
                        remote_img = urljoin(self.base_url, remote_img)

                # Miniatura lokalna
                thumb_path = ""
                if remote_img and hasattr(self, "save_thumbnail"):
                    thumb_path = self.save_thumbnail(remote_img, title)

                # Rozróżnienie lokalizacji (Willa Sixta vs Budynek Główny)
                venue_name = "Galeria Bielska BWA"
                address = "ul. 3 Maja 11, Bielsko-Biała"
                if "willi sixta" in full_txt.lower() or "willa sixta" in title.lower():
                    venue_name = "Willa Sixta (Galeria Bielska BWA)"
                    address = "ul. Mickiewicza 24, Bielsko-Biała"

                events.append({
                    "title": title,
                    "date": date_val,
                    "time_start": "10:00",
                    "venue": venue_name,
                    "address": address,
                    "price_range": "Wstęp wolny / Bilety w kasie",
                    "description": f"{category}: {title} w przestrzeni {venue_name}.",
                    "image_url": remote_img,
                    "thumbnail_url": thumb_path,
                    "url": event_url,
                    "source": self.source_name,
                    "organizer": "Galeria Bielska BWA"
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd krytyczny podczas parsowania: {e}")

        print(f"[{self.source_name}] Pomyślnie sparsowano {len(events)} wydarzeń i wystaw.")
        return events


if __name__ == "__main__":
    scraper = GaleriaBielskaPlScraper()
    results = scraper.fetch_events()
    print(f"\nŁącznie sparsowano: {len(results)} aktywnych pozycji")
    if results:
        print("\nPrzykładowy rekord:")
        print(json.dumps(results[0], indent=2, ensure_ascii=False))