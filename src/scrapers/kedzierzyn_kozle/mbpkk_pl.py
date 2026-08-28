from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

POLISH_MONTH_MAP = {
    "stycznia": 1, "styczeń": 1, "sty": 1,
    "lutego": 2, "luty": 2, "lut": 2,
    "marca": 3, "marzec": 3, "mar": 3,
    "kwietnia": 4, "kwiecień": 4, "kwi": 4,
    "maja": 5, "maj": 5,
    "czerwca": 6, "czerwiec": 6, "cze": 6,
    "lipca": 7, "lipiec": 7, "lip": 7,
    "sierpnia": 8, "sierpień": 8, "sie": 8,
    "września": 9, "wrzesień": 9, "wrz": 9,
    "października": 10, "październik": 10, "paź": 10, "paz": 10,
    "listopada": 11, "listopad": 11, "lis": 11,
    "grudnia": 12, "grudzień": 12, "gru": 12,
}

IGNORE_TITLES = [
    "informacja",
    "godziny pracy",
    "komunikat",
    "życzenia",
    "regulamin",
    "deklaracja dostępności"
]


class MbpKkPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="mbpkk_pl",
            base_url="https://mbpkk.pl"
        )
        self.events_url = "https://mbpkk.pl/aktualne-wydarzenia/"

    def _parse_polish_date(self, text: str) -> str:
        now = datetime.now()

        # 1. Termin: DD.MM.YYYY
        termin_match = re.search(r"Termin:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", text, re.IGNORECASE)
        if termin_match:
            d, m, y = termin_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # 2. Standardowy format DD.MM.YYYY
        d_match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
        if d_match:
            d, m, y = d_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # 3. Słowny format DD [miesiąc] (YYYY)
        month_pattern = "|".join(POLISH_MONTH_MAP.keys())
        word_match = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?\b", text, re.IGNORECASE)
        if word_match:
            d, m_name, y = word_match.groups()
            m = POLISH_MONTH_MAP[m_name.lower()]
            year = int(y) if y else (now.year if m >= now.month else now.year + 1)
            return f"{year}-{m:02d}-{int(d):02d}"

        # 4. DD.MM bez roku
        short_dot = re.search(r"\b(\d{1,2})\.(\d{1,2})\b", text)
        if short_dot:
            d, m = short_dot.groups()
            m_val = int(m)
            if 1 <= m_val <= 12 and 1 <= int(d) <= 31:
                year = now.year if m_val >= now.month else now.year + 1
                return f"{year}-{m_val:02d}-{int(d):02d}"

        return ""

    def _parse_event_time(self, text: str) -> str:
        time_match = re.search(r"godz(?:ina|\.)?\s*([01]?[0-9]|2[0-3])[:.]([0-5][0-9])", text, re.IGNORECASE)
        if time_match:
            h, m = time_match.groups()
            return f"{int(h):02d}:{m}"
        return "Według harmonogramu"

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        default_img = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"

        try:
            print(f"\n[{self.source_name}] Skanowanie wydarzeń MBP Kędzierzyn-Koźle...")
            resp = self.session.get(self.events_url, timeout=(3.0, 12.0), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")

            cards = soup.select("article, .post, .elementor-post, .event-item")
            if not cards:
                cards = soup.select(".content-area div.col-md-4, .site-main > div")

            for card in cards:
                for meta in card.select(".entry-meta, .post-meta, .author, .posted-on, time"):
                    meta.decompose()

                title_el = card.select_one("h2, h3, h4, .entry-title, .elementor-post__title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if len(title) < 5 or any(ignored in title.lower() for ignored in IGNORE_TITLES):
                    continue

                card_text = card.get_text(" ", strip=True)
                date_str = self._parse_polish_date(card_text)

                if not date_str or date_str < today_iso:
                    continue

                time_start = self._parse_event_time(card_text)

                link_el = card.select_one("a[href]")
                url = urljoin(self.base_url, link_el["href"]) if link_el else self.events_url

                img_el = card.select_one("img[src]")
                raw_image = ""
                if img_el:
                    src = img_el.get("src", "")
                    if src and not src.startswith("data:"):
                        raw_image = urljoin(self.base_url, src)

                thumb_path = self.save_thumbnail(raw_image, title, prefix="mbpkk") if raw_image else ""

                desc_el = card.select_one("p, .entry-summary, .elementor-post__excerpt")
                raw_desc = desc_el.get_text(" ", strip=True) if desc_el else card_text

                clean_desc = re.sub(r"^[A-ZŁŚŻŹ][a-ząćęłńóśźż]+\s+[A-ZŁŚŻŹ][a-ząćęłńóśźż]+\s+\d{4}-\d{2}-\d{2}T[^\s]+", "", raw_desc)
                clean_desc = clean_desc.replace("Czytaj więcej", "").strip(" |–- \n\t")

                print(f"  [MBP] {date_str} | {time_start} | {title[:35]}...")

                events.append({
                    "title": title,
                    "date_start": date_str,
                    "date_end": date_str,
                    "time_start": time_start,
                    "venue": "Miejska Biblioteka Publiczna w Kędzierzynie-Koźlu",
                    "address": "Rynek 3, Kędzierzyn-Koźle",
                    "price_range": "Wstęp wolny",
                    "description": clean_desc or f"Wydarzenie w MBP Kędzierzyn-Koźle: {title}.",
                    "image_url": thumb_path or raw_image or default_img,
                    "source_url": url,
                    "source": self.source_name,
                    "organizer": "Miejska Biblioteka Publiczna"
                })

            print(f"[{self.source_name}] Pomyślnie pobrano {len(events)} pozycji.")

        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania: {e}")

        return events
