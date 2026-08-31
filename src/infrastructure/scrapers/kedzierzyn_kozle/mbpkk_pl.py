import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper

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
    "informacja", "godziny pracy", "komunikat", "życzenia",
    "regulamin", "deklaracja dostępności", "ankieta", "e-skarbonka"
]

class MbpKkPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="mbpkk_pl",
            base_url="https://mbpkk.pl"
        )
        self.events_url = "/aktualne-wydarzenia/"

    def _parse_polish_date(self, text: str) -> tuple[str | None, str | None]:
        now = datetime.now()

        # 1. Zakres dat: DD.MM - DD.MM.YYYY
        range_match = re.search(r"(\d{1,2})\.(\d{1,2})\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if range_match:
            d1, m1, d2, m2, y = range_match.groups()
            return f"{y}-{int(m1):02d}-{int(d1):02d}", f"{y}-{int(m2):02d}-{int(d2):02d}"

        # 2. Termin: DD.MM.YYYY lub pojedyncza data DD.MM.YYYY
        d_match = re.search(r"(?:Termin:\s*)?\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text, re.IGNORECASE)
        if d_match:
            d, m, y = d_match.groups()
            iso_d = f"{y}-{int(m):02d}-{int(d):02d}"
            return iso_d, iso_d

        # 3. Słowny format: DD [miesiąc] (YYYY)
        month_pattern = "|".join(POLISH_MONTH_MAP.keys())
        word_match = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?\b", text, re.IGNORECASE)
        if word_match:
            d, m_name, y = word_match.groups()
            m = POLISH_MONTH_MAP[m_name.lower()]
            if y:
                year = int(y)
            else:
                if m >= now.month:
                    year = now.year
                elif now.month >= 11 and m <= 2:
                    year = now.year + 1
                else:
                    year = now.year
            iso_d = f"{year}-{m:02d}-{int(d):02d}"
            return iso_d, iso_d

        # 4. DD.MM bez roku
        short_dot = re.search(r"\b(\d{1,2})\.(\d{1,2})\b", text)
        if short_dot:
            d, m = short_dot.groups()
            m_val = int(m)
            if 1 <= m_val <= 12 and 1 <= int(d) <= 31:
                if m_val >= now.month:
                    year = now.year
                elif now.month >= 11 and m_val <= 2:
                    year = now.year + 1
                else:
                    year = now.year
                iso_d = f"{year}-{m_val:02d}-{int(d):02d}"
                return iso_d, iso_d

        return None, None

    def _parse_event_time(self, text: str) -> str:
        time_match = re.search(r"godz(?:ina|\.)?\s*([01]?[0-9]|2[0-3])[:.]([0-5][0-9])", text, re.IGNORECASE)
        if time_match:
            h, m = time_match.groups()
            return f"{int(h):02d}:{m}"
        return "Według harmonogramu"

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        seen_urls = set()
        today_iso = datetime.now().strftime("%Y-%m-%d")
        default_img = "/assets/placeholder.svg"

        print(f"[{self.source_name}] Skanowanie wydarzeń MBP Kędzierzyn-Koźle...")

        for page in range(1, 4):
            page_url = f"{self.events_url}page/{page}/" if page > 1 else self.events_url
            try:
                soup = self.get_soup(page_url)
            except Exception:
                break

            cards = soup.select("article, .post, .elementor-post, .event-item")
            if not cards:
                cards = soup.select(".content-area div.col-md-4, .site-main > div")
            if not cards:
                break

            for card in cards:
                for meta in card.select(".entry-meta, .post-meta, .author, .posted-on, time"):
                    meta.decompose()

                title_el = card.select_one("h2, h3, h4, .entry-title, .elementor-post__title")
                if not title_el:
                    continue

                title = re.sub(r"\s+", " ", title_el.get_text()).strip()
                if len(title) < 5 or any(ignored in title.lower() for ignored in IGNORE_TITLES):
                    continue

                card_text = card.get_text(" ", strip=True)
                d_start, d_end = self._parse_polish_date(card_text)

                check_date = d_end or d_start
                if not check_date or check_date < today_iso:
                    continue

                link_el = card.select_one("a[href]")
                full_url = urljoin(self.base_url, link_el["href"]) if link_el else self.base_url
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                time_start = self._parse_event_time(card_text)

                img_el = card.select_one("img[src]")
                raw_image = ""
                if img_el:
                    src = img_el.get("src", "")
                    if src and not src.startswith("data:"):
                        raw_image = urljoin(self.base_url, src)

                thumb_path = self.save_thumbnail(raw_image, title, prefix="mbpkk") if raw_image else ""

                desc_el = card.select_one("p, .entry-summary, .elementor-post__excerpt")
                raw_desc = desc_el.get_text(" ", strip=True) if desc_el else card_text
                clean_desc = re.sub(r"^[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+\s+\d{4}-\d{2}-\d{2}T[^\s]+", "", raw_desc)
                clean_desc = clean_desc.replace("Czytaj więcej", "").strip(" |–- \n\t")

                # Rozpoznawanie filii MBP
                venue = "Miejska Biblioteka Publiczna w Kędzierzynie-Koźlu"
                address = "Rynek 3, Kędzierzyn-Koźle"
                lower_card = card_text.lower()
                filia_match = re.search(r"filia\s*(?:nr\s*)?(\d+)", lower_card)
                if filia_match:
                    filia_nr = filia_match.group(1)
                    venue = f"MBP Filia nr {filia_nr}"
                    address = f"MBP Filia nr {filia_nr}, Kędzierzyn-Koźle"

                events.append({
                    "title": title,
                    "date_start": d_start,
                    "date_end": d_end,
                    "time_start": time_start,
                    "venue": venue,
                    "address": address,
                    "price_range": "Wstęp wolny",
                    "description": clean_desc or f"Wydarzenie w MBP Kędzierzyn-Koźle: {title}.",
                    "image_url": thumb_path or raw_image or default_img,
                    "source_url": full_url,
                    "source": self.source_name,
                    "organizer": "Miejska Biblioteka Publiczna"
                })

        print(f"[{self.source_name}] Zwrócono {len(events)} pozycji.")
        return events
