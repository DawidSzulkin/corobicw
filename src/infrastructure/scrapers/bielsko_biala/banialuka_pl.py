from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import urllib3

# Dodanie głównego katalogu projektu (portal/) do sys.path
ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.infrastructure.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BanialukaPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="banialuka_pl",
            base_url="https://banialuka.pl"
        )
        self.ajax_url = f"{self.base_url}/ajax/get-simple-repertoire"
        self.repertoire_page_url = f"{self.base_url}/repertuar"
        self.seen_signatures: Set[str] = set()
        self.details_cache: Dict[str, Dict[str, str]] = {}

    def _fetch_show_details(self, item: Tuple[str, str]) -> Tuple[str, Dict[str, str]]:
        show_url, title = item
        data = {"image_url": "", "description": "", "duration": "~60 min", "age": ""}
        if not show_url or show_url == self.repertoire_page_url:
            return show_url, data

        try:
            resp = self.session.get(show_url, timeout=(3.0, 8.0), verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser")
                
                # Pobranie plakatu / grafiki
                raw_image_url = ""
                for img in soup.select("img[src*='/uploads/attachments/'], img[src*='/uploads/']"):
                    src = img.get("src") or img.get("data-src", "")
                    if src and not any(ign in src.lower() for ign in ["logo", "herb", "sponsor", "bank", "pko", "slider", "decoration", "icon"]):
                        raw_image_url = urljoin(self.base_url, src)
                        break

                if not raw_image_url:
                    og = soup.select_one("meta[property='og:image']")
                    if og and og.get("content"):
                        raw_image_url = urljoin(self.base_url, og["content"])

                if raw_image_url:
                    thumb_path = self.save_thumbnail(raw_image_url, title, prefix="banialuka")
                    data["image_url"] = thumb_path or raw_image_url

                # Pobranie pełnego opisu
                desc_container = soup.select_one(".content, .entry-content, .show-desc, article, .wysiwyg, .spectacle__description")
                if desc_container:
                    paragraphs = [p.get_text(strip=True) for p in desc_container.select("p") if len(p.get_text(strip=True)) > 20]
                    if paragraphs:
                        data["description"] = "\n\n".join(paragraphs[:4])

                # Czas trwania
                full_text = soup.decode_contents()
                dur_m = re.search(r"czas\s+trwania:?\s*(\d+\s*(?:min|h))", full_text, re.IGNORECASE)
                if dur_m:
                    data["duration"] = dur_m.group(1)

        except Exception as e:
            print(f"[{self.source_name}] Błąd pobierania szczegółów '{title[:30]}': {e}")

        return show_url, data

    def fetch_events(self) -> List[Dict[str, Any]]:
        now = datetime.now()
        today_iso = now.strftime("%Y-%m-%d")
        current_year = now.year
        current_month = now.month
        self.seen_signatures.clear()
        self.details_cache.clear()

        print(f"\n[{self.source_name}] Pobieranie kalendarza Banialuki z endpointu AJAX...")

        ajax_headers = {
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.repertoire_page_url
        }

        try:
            resp = self.session.get(self.ajax_url, headers=ajax_headers, timeout=(4.0, 12.0), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code} z endpointu AJAX.")
                return []
            
            data = resp.json()
            html_content = data.get("html", "")
            if not html_content:
                print(f"[{self.source_name}] Pusta zawartość HTML w odpowiedzi.")
                return []
        except Exception as e:
            print(f"[{self.source_name}] Wyjątek podczas pobierania endpointu AJAX: {e}")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        articles = soup.find_all("article", class_="small-event-row")
        print(f"[{self.source_name}] Odnaleziono {len(articles)} wierszy spektakli w kalendarzu.")

        raw_entries = []
        unique_shows: Dict[str, str] = {}

        for art in articles:
            # 1. Ekstrakcja tytułu i odnośnika
            title = ""
            event_url = self.repertoire_page_url

            for a in art.find_all("a", href=True):
                href = a["href"]
                text = " ".join(a.get_text().split())
                if any(ign in text.lower() for ign in ["kup bilet", "rezerwuj", "bilety"]) or "bilety." in href or "repertoire.html" in href:
                    continue
                if "/spektakl/" in href or not title:
                    title = text.title()
                    event_url = urljoin(self.base_url, href)
                    if "/spektakl/" in href:
                        break

            if not title:
                continue

            # 2. Ekstrakcja daty
            day_el = art.select_one(".small-event-row__day")
            if not day_el:
                continue

            d_match = re.search(r"(\d{1,2})\.(\d{1,2})", day_el.get_text(strip=True))
            if not d_match:
                continue

            d_val, m_val = int(d_match.group(1)), int(d_match.group(2))
            target_year = current_year
            if m_val < current_month and current_month >= 8:
                target_year = current_year + 1

            try:
                event_date = datetime(target_year, m_val, d_val).date()
                date_val = event_date.strftime("%Y-%m-%d")
            except ValueError:
                continue

            if date_val < today_iso:
                continue

            # 3. Ekstrakcja godziny
            hour_el = art.select_one(".small-event-row__hour")
            time_val = hour_el.get_text(strip=True) if hour_el else "10:00"

            # 4. Sygnatura deduplikacji
            sig = f"{date_val}_{time_val}_{title.lower()}"
            if sig in self.seen_signatures:
                continue
            self.seen_signatures.add(sig)

            raw_entries.append({
                "title": title,
                "date": date_val,
                "time_start": time_val,
                "url": event_url
            })

            if event_url != self.repertoire_page_url and event_url not in unique_shows:
                unique_shows[event_url] = title

        # Deep Scraping szczegółów spektakli
        if unique_shows:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(self._fetch_show_details, (url, t)) for url, t in unique_shows.items()]
                for fut in as_completed(futures):
                    try:
                        u, d_obj = fut.result()
                        if d_obj:
                            self.details_cache[u] = d_obj
                    except Exception:
                        pass

        events = []
        for entry in raw_entries:
            d_info = self.details_cache.get(entry["url"], {})
            desc = d_info.get("description", "")
            if len(desc) < 30:
                desc = f"Spektakl Teatru Lalek Banialuka: {entry['title']}. Bilety dostępne w kasie teatru oraz online."

            events.append({
                "title": entry["title"],
                "date_start": entry["date"],
                "date_end": entry["date"],
                "time_start": entry["time_start"],
                "venue": "Teatr Lalek Banialuka",
                "address": "ul. Mickiewicza 20, Bielsko-Biała",
                "price_range": "Bilety płatne (Kasa / Bilety24)",
                "description": desc,
                "image_url": d_info.get("image_url", ""),
                "source_url": entry["url"],
                "source": self.source_name,
                "organizer": "Teatr Lalek Banialuka",
                "category": "Teatr i Spektakle"
            })

        print(f"[{self.source_name}] Pomyślnie sparsowano {len(events)} nadchodzących spektakli.")
        return events

if __name__ == "__main__":
    scraper = BanialukaPlScraper()
    evs = scraper.fetch_events()
    print(f"\nPobrano łącznie {len(evs)} wydarzeń. Pierwsze 3:")
    for e in evs[:3]:
        print(" -", e["date_start"], e["time_start"], e["title"], "| Plakat:", bool(e["image_url"]), "| Link:", e["source_url"])