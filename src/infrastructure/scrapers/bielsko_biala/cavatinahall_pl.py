from datetime import datetime
import html
import os
import re
import sys
from typing import Any, Dict, List, Set
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.infrastructure.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CavatinaHallPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="cavatinahall_pl",
            base_url="https://cavatinahall.pl"
        )
        self.api_url = f"{self.base_url}/wp-json/wp/v2/events"
        self.seen_signatures: Set[str] = set()

    def _parse_event_datetime(self, item: Dict[str, Any]) -> tuple:
        acf = item.get("acf") or {}
        event_dt_str = acf.get("event_datetime")

        if event_dt_str:
            try:
                dt = datetime.strptime(str(event_dt_str).strip(), "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
            except ValueError:
                pass

        event_date_raw = acf.get("event_date")
        event_time_raw = acf.get("event_time", "19:00:00")

        if event_date_raw and len(str(event_date_raw)) == 8:
            try:
                dt = datetime.strptime(str(event_date_raw), "%Y%m%d")
                t_str = "19:00"
                if event_time_raw:
                    t_parts = str(event_time_raw).split(":")
                    if len(t_parts) >= 2:
                        t_str = f"{int(t_parts[0]):02d}:{t_parts[1]}"
                return dt.strftime("%Y-%m-%d"), t_str
            except ValueError:
                pass

        return "", "19:00"

    def _extract_image_url(self, item: Dict[str, Any]) -> str:
        yoast = item.get("yoast_head_json") or {}
        og_images = yoast.get("og_image") or []
        if og_images and isinstance(og_images, list) and og_images[0].get("url"):
            return og_images[0]["url"]

        embedded = item.get("_embedded") or {}
        featured = embedded.get("wp:featuredmedia") or []
        if featured and isinstance(featured, list) and featured[0].get("source_url"):
            return featured[0]["source_url"]

        return ""

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie repertuaru Cavatina Hall...")

        page = 1
        max_pages = 10

        while page <= max_pages:
            params = {
                "per_page": 50,
                "page": page
            }
            try:
                resp = self.session.get(self.api_url, params=params, timeout=(4.0, 10.0), verify=False)

                if resp.status_code in [400, 404]:
                    break
                if resp.status_code != 200:
                    print(f"[{self.source_name}] HTTP {resp.status_code} przy stronie {page}")
                    break

                items = resp.json()
                if not items or not isinstance(items, list):
                    break

                for item in items:
                    event_url = item.get("link", f"{self.base_url}/wydarzenia/")
                    
                    # Odrzucenie angielskich duplikatów
                    if "/en/" in event_url or "/en-" in event_url:
                        continue

                    raw_title = item.get("title", {}).get("rendered", "")
                    title = html.unescape(raw_title).strip()
                    if len(title) < 2:
                        continue

                    date_iso, time_str = self._parse_event_datetime(item)
                    if not date_iso or date_iso < today_iso:
                        continue

                    sig = f"{date_iso}_{time_str}_{title.lower()}"
                    if sig in self.seen_signatures:
                        continue
                    self.seen_signatures.add(sig)

                    full_remote_img = self._extract_image_url(item)
                    thumb_path = self.save_thumbnail(full_remote_img, title, prefix="cavatina")

                    raw_content = item.get("content", {}).get("rendered", "")
                    if raw_content:
                        c_soup = BeautifulSoup(raw_content, "html.parser")
                        clean_desc = c_soup.get_text("\n\n", strip=True)
                        desc = re.sub(r"\s+", " ", clean_desc).strip()
                        if len(desc) > 300:
                            desc = desc[:300].rsplit(" ", 1)[0] + "..."
                    else:
                        desc = f"Koncert i wydarzenie muzyczne w Cavatina Hall: {title}."

                    events.append({
                        "title": title,
                        "date_start": date_iso,
                        "date_end": date_iso,
                        "time_start": time_str,
                        "venue": "Cavatina Hall",
                        "address": "ul. Dworkowa 2, Bielsko-Biała",
                        "price_range": "Bilety płatne (Kasa / Eventim / Cavatina)",
                        "description": desc,
                        "image_url": thumb_path or full_remote_img,
                        "source_url": event_url,
                        "source": self.source_name,
                        "organizer": "Cavatina Hall"
                    })

                page += 1

            except Exception as e:
                print(f"[{self.source_name}] Błąd strony {page}: {e}")
                break

        print(f"[{self.source_name}] Pomyślnie sparsowano {len(events)} aktywnych wydarzeń Cavatina Hall.")
        return events
