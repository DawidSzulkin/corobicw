from datetime import datetime
import io
import json
import os
import re
import sys
from typing import Any, Dict, List, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
import requests
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
        self.session = requests.Session()
        # Standardowe nagłówki przeglądarkowe (bez globalnego wymuszania AJAX/JSON)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pl,en-US;q=0.7,en;q=0.3"
        })
        self.seen_signatures: Set[str] = set()
        self.posters_cache: Dict[str, str] = {}
        
        self.thumb_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../docs/assets/thumbnails"))
        os.makedirs(self.thumb_dir, exist_ok=True)

    def _get_show_poster(self, show_url: str, title: str) -> str:
        """Pobiera i kompresuje plakat do WebP, priorytetyzując cache dyskowy i pamięciowy."""
        safe_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", title.lower()).strip("_")
        filename = f"banialuka_{safe_slug}.webp"
        disk_path = os.path.join(self.thumb_dir, filename)
        web_path = f"/assets/thumbnails/{filename}"

        # 1. Sprawdzenie cache dyskowego (0 zapytań HTTP)
        if os.path.exists(disk_path):
            return web_path

        # 2. Sprawdzenie cache w pamięci procesu
        if title in self.posters_cache:
            return self.posters_cache[title]

        if not show_url or show_url == self.repertoire_page_url:
            return ""

        try:
            print(f"[{self.source_name}] Pobieranie metadanych plakatu dla: {title}...")
            resp = self.session.get(show_url, timeout=(3.05, 6), verify=False)
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
                    print(f"[{self.source_name}] Kompresja miniatury ({raw_image_url.split('/')[-1]})...")
                    img_resp = self.session.get(raw_image_url, timeout=(3.05, 12), verify=False)
                    if img_resp.status_code == 200:
                        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                        max_w = 400
                        if img.width > max_w:
                            ratio = max_w / float(img.width)
                            new_h = int(float(img.height) * float(ratio))
                            img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)
                        
                        img.save(disk_path, "WEBP", quality=75, optimize=True)
                        self.posters_cache[title] = web_path
                        return web_path
        except Exception as e:
            print(f"[{self.source_name}] Błąd przetwarzania miniatury dla '{title}': {e}")

        self.posters_cache[title] = ""
        return ""

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now()
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie repertuaru Teatru Lalek Banialuka...")

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

        for year, month in months_to_check:
            try:
                payload = {"year": year, "month": month}
                resp = self.session.post(self.ajax_url, data=payload, headers=ajax_headers, timeout=(3.05, 10), verify=False)
                if resp.status_code != 200:
                    continue

                res_json = resp.json()
                html_content = res_json.get("html", "")
                if not html_content:
                    continue

                soup = BeautifulSoup(html_content, "html.parser")
                articles = soup.find_all("article", class_="event-row")

                for art in articles:
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
                    links = art.find_all("a", href=True)
                    for a in links:
                        text_lower = a.get_text(strip=True).lower()
                        if "więcej" in text_lower or "spektakl" in a["href"]:
                            event_url = urljoin(self.base_url, a["href"])
                            break

                    image_url = self._get_show_poster(event_url, title)

                    age_info = ""
                    for cell in art.select(".event-row__cell"):
                        cell_txt = cell.get_text(strip=True)
                        if "+" in cell_txt or "lat" in cell_txt.lower():
                            age_info = f" (Wiek: {cell_txt})"
                            break

                    events.append({
                        "title": title,
                        "date": date_val,
                        "time_start": time_val,
                        "venue": "Teatr Lalek Banialuka",
                        "address": "ul. Mickiewicza 20, Bielsko-Biała",
                        "price_range": "Bilety płatne (Kasa / Bilety24)",
                        "description": f"Spektakl Teatru Lalek Banialuka: {title}{age_info}.",
                        "image_url": image_url,
                        "url": event_url,
                        "source": self.source_name,
                        "organizer": "Teatr Lalek Banialuka"
                    })

            except Exception as e:
                print(f"[{self.source_name}] Błąd przetwarzania {year}-{month:02d}: {e}")

        print(f"[{self.source_name}] Pomyślnie sparsowano {len(events)} spektakli.")
        return events


if __name__ == "__main__":
    scraper = BanialukaPlScraper()
    results = scraper.fetch_events()
    print(f"\nŁącznie sparsowano: {len(results)} aktywnych spektakli")
    if results:
        print("\nPrzykładowy rekord:")
        print(json.dumps(results[0], indent=2, ensure_ascii=False))