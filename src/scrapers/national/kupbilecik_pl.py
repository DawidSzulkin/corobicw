from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CITY_SEARCH_QUERIES = {
    "kedzierzyn_kozle": "Kędzierzyn Koźle",
    "bielsko_biala": "Bielsko-Biała",
    "opole": "Opole",
    "gliwice": "Gliwice",
    "katowice": "Katowice",
    "wroclaw": "Wrocław",
    "krakow": "Kraków",
}

CITY_MATCH_PATTERNS = {
    "kedzierzyn_kozle": ["kędzierzyn", "kedzierzyn", "koźle", "kozle"],
    "bielsko_biala": ["bielsko", "bielsku"],
    "opole": ["opole", "opolu"],
    "gliwice": ["gliwice", "gliwicach"],
    "katowice": ["katowice", "katowicach"],
    "wroclaw": ["wrocław", "wroclaw"],
    "krakow": ["kraków", "krakow"],
}


class KupBilecikPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="kupbilecik_pl",
            base_url="https://www.kupbilecik.pl"
        )
        self.city_tag = city_tag.strip().lower()
        self.partner_id = partner_id
        self.city_query = CITY_SEARCH_QUERIES.get(self.city_tag, self.city_tag.replace("_", " ").title())
        self.city_patterns = CITY_MATCH_PATTERNS.get(self.city_tag, [self.city_tag.replace("_", "")])
        self.events_url = f"{self.base_url}/szukaj/?q={quote_plus(self.city_query)}"

    def _format_url(self, raw_url: str) -> str:
        clean_url = urljoin(self.base_url, raw_url)
        if self.partner_id:
            separator = "&" if "?" in clean_url else "?"
            return f"{clean_url}{separator}pv={self.partner_id}"
        return clean_url

    def _is_matching_city(self, text: str) -> bool:
        norm = text.lower()
        return any(pattern in norm for pattern in self.city_patterns)

    def _parse_date(self, text: str) -> str:
        dot_match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
        if dot_match:
            d, m, y = dot_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        iso_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", text)
        if iso_match:
            return iso_match.group(1)

        return ""

    def _parse_time(self, text: str) -> str:
        match = re.search(r"godz(?:ina|\.)?\s*([01]?[0-9]|2[0-3])[:.]([0-5][0-9])", text, re.IGNORECASE)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"

        match_simple = re.search(r"\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b", text)
        if match_simple:
            return f"{int(match_simple.group(1)):02d}:{match_simple.group(2)}"

        return "Według harmonogramu"

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")

        try:
            resp = self.session.get(self.events_url, timeout=(3.05, 10), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")
            seen_urls = set()
            event_links = soup.select("a[href*='/imprezy/'], a[href*='/wydarzenia/'], a[href*='/bilet/']")

            for a_tag in event_links:
                href = a_tag.get("href", "")
                if not href or not re.search(r"/(?:imprezy|wydarzenia)/\d+/", href):
                    continue

                full_url = self._format_url(href)
                if full_url in seen_urls:
                    continue

                row = a_tag
                for _ in range(5):
                    parent = row.parent
                    if not parent or parent.name in ["body", "html", "main"]:
                        break
                    row = parent
                    if "Kup bilet" in row.get_text() and ("godz" in row.get_text() or re.search(r"\d{1,2}\s+[a-ząćęłńóśźż]{3,}", row.get_text())):
                        break

                row_text = row.get_text(" ", strip=True)
                if not self._is_matching_city(row_text):
                    continue

                date_str = self._parse_date(row_text)
                if not date_str or date_str < today_iso:
                    continue

                title = ""
                for link in row.select("a[href*='/imprezy/'], a[href*='/wydarzenia/']"):
                    txt = link.get_text(strip=True)
                    if len(txt) > 3 and txt.lower() not in ["kup bilet", "bilety", "szczegóły", "więcej"]:
                        title = txt
                        break

                if not title:
                    header = row.select_one("h2, h3, h4, strong, b")
                    if header and len(header.get_text(strip=True)) > 3:
                        title = header.get_text(strip=True)

                if not title:
                    continue

                seen_urls.add(full_url)
                time_start = self._parse_time(row_text)

                venue = "Obiekt widowiskowy"
                venue_el = row.select_one("a[href*='/obiekty/']")
                if venue_el:
                    venue = venue_el.get_text(strip=True)
                else:
                    m_loc = re.search(rf"(?:{self.city_query}|Koźle)\s*[\n\r,·-]?\s*([A-ZŁŚŻŹ0-9][\w\s.\-–]+?)(?:Kup bilet|Od\s*\d|\d+\s*zł|$)", row_text)
                    if m_loc and 2 < len(m_loc.group(1).strip()) < 50:
                        venue = m_loc.group(1).strip(" –-.,")

                image_url = ""
                img_el = row.select_one("img[src], img[data-src]")
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src", "")
                    if not src.startswith("data:"):
                        image_url = urljoin(self.base_url, src)

                thumb_path = self.save_thumbnail(image_url, title, prefix=f"kupbilecik_{self.city_tag}") if image_url else ""

                events.append({
                    "title": title,
                    "date_start": date_str,
                    "date_end": date_str,
                    "time_start": time_start,
                    "venue": venue,
                    "address": f"{venue}, {self.city_query}",
                    "price_range": "Bilety płatne",
                    "description": f"Wydarzenie biletowane: {title}. Miejsce: {venue}.",
                    "image_url": thumb_path or image_url,
                    "source_url": full_url,
                    "source": self.source_name,
                    "organizer": "KupBilecik.pl"
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania: {e}")

        print(f"[{self.source_name}] Sparsowano {len(events)} wydarzeń dla '{self.city_tag}'.")
        return events
