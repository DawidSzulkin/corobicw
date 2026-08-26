from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
import re
import sys
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BanialukaPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="banialuka_pl",
            base_url="https://banialuka.pl"
        )
        self.ajax_url = f"{self.base_url}/ajax/get-repertoire"
        self.repertoire_page_url = f"{self.base_url}/repertuar"
        self.seen_signatures: Set[str] = set()
        self.posters_cache: Dict[str, str] = {}

    def _fetch_poster_for_url(self, item: Tuple[str, str]) -> Tuple[str, str]:
        show_url, title = item
        if not show_url or show_url == self.repertoire_page_url:
            return show_url, ""

        try:
            resp = self.session.get(show_url, timeout=(2.0, 5.0), verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                raw_image_url = ""
                for img in soup.select("img[src*='/uploads/attachments/']"):
                    src = img.get("src", "")
                    if not any(ign in src.lower() for ign in ["logo", "herb", "sponsor", "bank", "pko", "slider", "decoration"]):
                        raw_image_url = urljoin(self.base_url, src)
                        break

                if not raw_image_url:
                    og = soup.select_one("meta[property='og:image']")
                    if og and og.get("content"):
                        raw_image_url = urljoin(self.base_url, og["content"])

                if raw_image_url:
                    thumb_path = self.save_thumbnail(raw_image_url, title, prefix="banialuka")
                    return show_url, (thumb_path or raw_image_url)

        except Exception as e:
            print(f"[{self.source_name}] Pominięto plakat dla '{title[:30]}': {e}")

        return show_url, ""

    def fetch_events(self) -> List[Dict[str, Any]]:
        today_iso = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now()
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie kalendarza Banialuki...")

        months_to_check = []
        for offset in range(4):
            m = (now.month - 1 + offset) % 12 + 1
            y = now.year + ((now.month - 1 + offset) // 12)
            months_to_check.append((y, m))

        ajax_headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.repertoire_page_url,
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }

        raw_entries = []
        unique_shows: Dict[str, str] = {}

        for year, month in months_to_check:
            try:
                payload = {"year": year, "month": month}
                resp = self.session.post(self.ajax_url, data=payload, headers=ajax_headers, timeout=(2.0, 5.0), verify=False)
                if resp.status_code != 200:
                    continue

                html_content = resp.json().get("html", "")
                if not html_content:
                    continue

                soup = BeautifulSoup(html_content, "html.parser")
                for art in soup.find_all("article", class_="event-row"):
                    title_el = art.select_one(".row-title, h3")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True).title()

                    date_val = ""
                    date_el = art.select_one(".event-row__cell--date .row-date")
                    if date_el:
                        d_match = re.search(r"(\d{1,2})\.(\d{1,2})", date_el.get_text(strip=True))
                        if d_match:
                            d, m = d_match.groups()
                            date_val = f"{year}-{int(m):02d}-{int(d):02d}"

                    if not date_val or date_val < today_iso:
                        continue

                    time_val = "10:00"
                    time_el = art.select_one(".event-row__cell--time .row-date")
                    if time_el:
                        time_val = time_el.get_text(strip=True)

                    sig = f"{date_val}_{time_val}_{title.lower()}"
                    if sig in self.seen_signatures:
                        continue
                    self.seen_signatures.add(sig)

                    event_url = self.repertoire_page_url
                    for a in art.find_all("a", href=True):
                        text_lower = a.get_text(strip=True).lower()
                        if "więcej" in text_lower or "spektakl" in a["href"]:
                            event_url = urljoin(self.base_url, a["href"])
                            break

                    age_info = ""
                    for cell in art.select(".event-row__cell"):
                        cell_txt = cell.get_text(strip=True)
                        if "+" in cell_txt or "lat" in cell_txt.lower():
                            age_info = f" (Wiek: {cell_txt})"
                            break

                    raw_entries.append({
                        "title": title,
                        "date": date_val,
                        "time_start": time_val,
                        "url": event_url,
                        "age_info": age_info
                    })

                    if event_url != self.repertoire_page_url and event_url not in unique_shows:
                        unique_shows[event_url] = title

            except Exception as e:
                print(f"[{self.source_name}] Błąd pobierania {year}-{month:02d}: {e}")

        if unique_shows:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(self._fetch_poster_for_url, (url, title)) for url, title in unique_shows.items()]
                for fut in as_completed(futures):
                    try:
                        u, img = fut.result()
                        if img:
                            self.posters_cache[u] = img
                    except Exception:
                        pass

        events = []
        for entry in raw_entries:
            img_path = self.posters_cache.get(entry["url"], "")
            events.append({
                "title": entry["title"],
                "date_start": entry["date"],
                "date_end": entry["date"],
                "time_start": entry["time_start"],
                "venue": "Teatr Lalek Banialuka",
                "address": "ul. Mickiewicza 20, Bielsko-Biała",
                "price_range": "Bilety płatne (Kasa / Bilety24)",
                "description": f"Spektakl Teatru Lalek Banialuka: {entry['title']}{entry['age_info']}.",
                "image_url": img_path,
                "source_url": entry["url"],
                "source": self.source_name,
                "organizer": "Teatr Lalek Banialuka"
            })

        print(f"[{self.source_name}] Pomyślnie sparsowano {len(events)} spektakli.")
        return events
