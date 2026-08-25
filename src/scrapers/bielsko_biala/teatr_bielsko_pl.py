from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Set
import requests
import urllib3

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# Zapewnia widoczność katalogu głównego projektu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TeatrBielskoPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="teatr_bielsko_pl",
            base_url="https://teatr.bielsko.pl"
        )
        self.api_url = f"{self.base_url}/api/repertoire"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.base_url}/repertuar"
        })
        self.seen_signatures: Set[str] = set()
        self.posters_cache: Dict[str, str] = {}

    def _parse_datetime(self, iso_str: str) -> tuple[str, str]:
        """Konwertuje timestamp ISO UTC na datę i godzinę w strefie Europe/Warsaw."""
        if not iso_str:
            return "", "Według harmonogramu"
        try:
            clean_iso = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_iso)
            if ZoneInfo and dt.tzinfo:
                dt = dt.astimezone(ZoneInfo("Europe/Warsaw"))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except Exception:
            date_part = iso_str[:10] if len(iso_str) >= 10 else ""
            time_part = iso_str[11:16] if len(iso_str) >= 16 else "Według harmonogramu"
            return date_part, time_part

    def _get_poster_for_slug(self, slug: str) -> str:
        """Pobiera główny URL plakatu spektaklu ze strumienia RSC."""
        if not slug:
            return ""
        if slug in self.posters_cache:
            return self.posters_cache[slug]

        try:
            show_url = f"{self.base_url}/spektakl/{slug}"
            rsc_headers = {
                "RSC": "1",
                "User-Agent": self.session.headers["User-Agent"],
                "Accept": "*/*"
            }
            resp = self.session.get(show_url, headers=rsc_headers, timeout=8, verify=False)
            if resp.status_code == 200:
                # 1. Priorytet: dedykowany CDN mediów teatru
                cdn_images = re.findall(
                    r'https://[^\s"\'<>]*(?:teapp\.pl|teatr\.bielsko\.pl)[^\s"\'<>]+/uploads/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)',
                    resp.text,
                    re.IGNORECASE
                )
                
                # 2. Fallback: jakikolwiek obrazek poza szablonowym ogimage/logo
                if not cdn_images:
                    cdn_images = [
                        img for img in re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)', resp.text, re.IGNORECASE)
                        if not any(ign in img.lower() for ign in ["ogimage", "logo", "favicon", "icon", "placeholder"])
                    ]

                if cdn_images:
                    poster_url = cdn_images[0]
                    self.posters_cache[slug] = poster_url
                    return poster_url
        except Exception as e:
            print(f"[{self.source_name}] Błąd pobierania grafiki dla {slug}: {e}")

        self.posters_cache[slug] = ""
        return ""

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie repertuaru i grafik spektakli...")

        try:
            resp = self.session.get(self.api_url, verify=False, timeout=12)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP API: {resp.status_code}")
                return events

            data = resp.json()
            raw_items = data.get("events", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            for item in raw_items:
                if item.get("hiddenFromRepertoire"):
                    continue

                raw_title = item.get("title") or item.get("showEvent", {}).get("title", "")
                title = re.sub(r"\s+", " ", raw_title.replace("\xa0", " ")).strip()
                if not title:
                    continue

                raw_date = item.get("date", "")
                date_str, time_str = self._parse_datetime(raw_date)

                if not date_str or date_str < today_iso:
                    continue

                sig = f"{date_str}_{time_str}_{title.lower()}"
                if sig in self.seen_signatures:
                    continue
                self.seen_signatures.add(sig)

                # Ścieżka podglądu spektaklu
                slug = item.get("showEvent", {}).get("slug", "")
                event_url = f"{self.base_url}/spektakl/{slug}" if slug else f"{self.base_url}/repertuar"

                # Pobranie plakatu z RSC
                image_url = self._get_poster_for_slug(slug)

                # Scena
                stage_name = item.get("stage", {}).get("name") if item.get("stage") else None
                venue = f"Teatr Polski ({stage_name})" if stage_name else "Teatr Polski w Bielsku-Białej"

                # Czas trwania i bilety
                free_seats = item.get("freeSeats", 0)
                duration = item.get("duration")
                price_info = "Bilety wyprzedane" if (free_seats == 0 and item.get("status") == "sold_out") else "Bilety płatne (Kasa / Online)"

                desc_parts = [f"Spektakl: {title}."]
                if stage_name:
                    desc_parts.append(f"Scena: {stage_name}.")
                if duration:
                    desc_parts.append(f"Czas trwania: {duration} min.")
                description = " ".join(desc_parts)

                events.append({
                    "title": title,
                    "date": date_str,
                    "time_start": time_str,
                    "venue": venue,
                    "address": "ul. 1 Maja 1, Bielsko-Biała",
                    "price_range": price_info,
                    "description": description,
                    "image_url": image_url,
                    "url": event_url,
                    "source": self.source_name,
                    "organizer": "Teatr Polski w Bielsku-Białej"
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd pobierania: {e}")

        miniatury_count = len([e for e in events if e.get("image_url")])
        print(f"[{self.source_name}] Sparsowano: {len(events)} spektakli (znalezionych miniatur: {miniatury_count}).")
        return events


if __name__ == "__main__":
    scraper = TeatrBielskoPlScraper()
    results = scraper.fetch_events()
    print(f"\nWyniki ({len(results)}):\n")
    if results:
        print(json.dumps(results[:2], indent=2, ensure_ascii=False))