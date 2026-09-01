from datetime import datetime
import os
import re
import sys
from typing import Any, Dict, List, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GaleriaBielskaPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="galeriabielska_pl",
            base_url="https://galeriabielska.pl"
        )
        self.calendar_url = f"{self.base_url}/kalendarium/"
        self.seen_signatures: Set[str] = set()

    def _parse_date(self, text: str, current_year: int, current_month: int) -> str:
        match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", text)
        if not match:
            return ""
        day, month, year = match.groups()
        m = int(month)
        d = int(day)
        y = int(year) if year else (current_year if m >= current_month else current_year + 1)
        try:
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            return ""

    def _fetch_event_details(self, url: str) -> Dict[str, Any]:
        details = {"description": "", "time_start": "10:00", "price": "Wst?p wolny / Bilety w kasie"}
        try:
            r = self.session.get(url, timeout=(4.0, 10.0), verify=False)
            if r.status_code == 200:
                s = BeautifulSoup(r.content, "html.parser")
                content_div = s.select_one(".content, .entry-content, article, .event-details")
                if content_div:
                    paragraphs = [p.get_text(" ", strip=True) for p in content_div.select("p") if len(p.get_text(strip=True)) > 20]
                    if paragraphs:
                        details["description"] = "\n\n".join(paragraphs[:4])

                txt = s.get_text(" ", strip=True)
                time_m = re.search(r"godz(?:ina|\.)?\s*(\d{1,2}[:.]\d{2})", txt, re.IGNORECASE)
                if time_m:
                    details["time_start"] = time_m.group(1).replace(".", ":")
                if "bezp?atn" in txt.lower() or "wst?p wolny" in txt.lower():
                    details["price"] = "Wst?p bezp?atny"
        except Exception:
            pass
        return details

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        now = datetime.now()
        today_iso = now.strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie kalendarium Galerii Bielskiej BWA...")
        try:
            resp = self.session.get(self.calendar_url, timeout=(4.0, 10.0), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] B??d HTTP {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.content, "html.parser")
            items = soup.select("ul.eventlist a.event")

            for a in items:
                if "-past" in a.get("class", []):
                    continue

                event_url = urljoin(self.base_url, a.get("href", ""))
                if not event_url or event_url == self.calendar_url:
                    continue

                txt_container = a.select_one(".event_txt")
                if not txt_container:
                    continue

                full_txt = txt_container.get_text(" ", strip=True)
                date_start = self._parse_date(full_txt, current_year=now.year, current_month=now.month)
                date_end = date_start

                range_match = re.search(r"do\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", full_txt)
                if range_match:
                    end_d, end_m, end_y = range_match.groups()
                    m_val = int(end_m)
                    end_year = int(end_y) if end_y else (now.year if m_val >= now.month else now.year + 1)
                    end_iso = f"{end_year:04d}-{m_val:02d}-{int(end_d):02d}"
                    if end_iso >= today_iso:
                        date_end = end_iso
                        if not date_start or date_start < today_iso:
                            date_start = today_iso

                if not date_start or (date_end and date_end < today_iso):
                    continue

                cat_el = a.select_one(".event_pix")
                category = cat_el.get_text(strip=True) if cat_el else "Wystawa"

                title_el = a.select_one(".event_title, .event_titlepart")
                if title_el:
                    title = title_el.get_text(" ", strip=True)
                else:
                    title = re.sub(r"\d{1,2}\.\d{1,2}(?:\.\d{4})?.*", "", full_txt).strip() or full_txt[:60]
                title = re.sub(r"\s+", " ", title).strip()

                sig = f"{date_start}_{title.lower()}"
                if sig in self.seen_signatures:
                    continue
                self.seen_signatures.add(sig)

                img_el = a.select_one("img")
                remote_img = ""
                if img_el:
                    src_c = img_el.get("src") or img_el.get("data-src") or ""
                    if src_c:
                        remote_img = urljoin(self.base_url, src_c)

                thumb_path = self.save_thumbnail(remote_img, title, prefix="galeriabielska") if remote_img else ""

                venue_name = "Galeria Bielska BWA"
                address = "ul. 3 Maja 11, Bielsko-Bia?a"
                if "willi sixta" in full_txt.lower() or "willa sixta" in title.lower():
                    venue_name = "Willa Sixta (Galeria Bielska BWA)"
                    address = "ul. Mickiewicza 24, Bielsko-Bia?a"

                sub_data = self._fetch_event_details(event_url)
                desc = sub_data["description"] if len(sub_data["description"]) > 30 else f"{category}: {title} w przestrzeni {venue_name}."

                events.append({
                    "title": title,
                    "date_start": date_start,
                    "date_end": date_end or date_start,
                    "time_start": sub_data["time_start"],
                    "venue": venue_name,
                    "address": address,
                    "price_range": sub_data["price"],
                    "description": desc,
                    "image_url": thumb_path or remote_img,
                    "source_url": event_url,
                    "source": self.source_name,
                    "organizer": "Galeria Bielska BWA",
                    "category": category
                })
        except Exception as e:
            print(f"[{self.source_name}] B??d krytyczny: {e}")

        print(f"[{self.source_name}] Sparsowano {len(events)} rekord?w.")
        return events
