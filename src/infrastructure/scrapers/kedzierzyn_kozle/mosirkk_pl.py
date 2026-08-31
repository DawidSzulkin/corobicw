import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper

MONTHS_PL = {
    "stycznia": 1, "styczeń": 1, "styczen": 1, "sty": 1,
    "lutego": 2, "luty": 2, "lut": 2,
    "marca": 3, "marzec": 3, "mar": 3,
    "kwietnia": 4, "kwiecień": 4, "kwiecien": 4, "kwi": 4,
    "maja": 5, "maj": 5,
    "czerwca": 6, "czerwiec": 6, "cze": 6,
    "lipca": 7, "lipiec": 7, "lip": 7,
    "sierpnia": 8, "sierpień": 8, "sierpien": 8, "sie": 8,
    "września": 9, "wrzesień": 9, "wrzesien": 9, "wrz": 9,
    "października": 10, "październik": 10, "pazdziernik": 10, "paź": 10, "paz": 10,
    "listopada": 11, "listopad": 11, "lis": 11,
    "grudnia": 12, "grudzień": 12, "grudzien": 12, "gru": 12,
}

IGNORE_KEYWORDS = [
    "przetarg", "zapytanie ofertowe", "sanepid", "komunikat",
    "awaria", "przerwa techniczna", "grafik", "cennik", "regulamin"
]

class MosirKkPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="mosirkk_pl",
            base_url="https://www.mosirkk.pl"
        )
        self.calendar_url = "/imprezy/kalendarz-imprez-sportowych-mosir"
        self.news_url = "/aktualnosci"

    def _extract_venue_info(self, text: str) -> tuple[str, str]:
        lower = text.lower()
        if "kuźniczk" in lower or "kuzniczk" in lower or "grunwaldzk" in lower:
            return "Stadion Miejski Kuźniczka", "ul. Grunwaldzka 71, Kędzierzyn-Koźle"
        elif "azoty" in lower or "mostowa" in lower:
            return "Hala Widowiskowo-Sportowa Azoty", "ul. Mostowa 1, Kędzierzyn-Koźle"
        elif "śródmieści" in lower or "srodmiesci" in lower:
            return "Hala Sportowa Śródmieście", "al. Jana Pawła II 29, Kędzierzyn-Koźle"
        elif "wodne okko" in lower or "saun" in lower or "basen" in lower or "pływalni" in lower:
            return "Kryta Pływalnia / Wodne oKKo", "al. Jana Pawła II, Kędzierzyn-Koźle"
        elif "kort" in lower or "tenis" in lower:
            return "Korty Tenisowe MOSiR", "al. Jana Pawła II 29, Kędzierzyn-Koźle"
        return "Obiekty MOSiR Kędzierzyn-Koźle", "al. Jana Pawła II 29, Kędzierzyn-Koźle"

    def _parse_term_text(self, term_text: str, default_year: int) -> tuple[str | None, str | None]:
        clean = re.sub(r"\s+", " ", term_text).strip().lower()
        
        # 1. Zakres dni: "2 - 15 luty" lub "2-15 lutego"
        range_match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([a-ząćęłńóśźż]+)(?:\s+(\d{4}))?", clean)
        if range_match:
            d1, d2, m_name, y = range_match.groups()
            m_num = MONTHS_PL.get(m_name)
            year = int(y) if y else default_year
            if m_num:
                return f"{year}-{m_num:02d}-{int(d1):02d}", f"{year}-{m_num:02d}-{int(d2):02d}"

        # 2. Pojedynczy dzień: "14 luty" lub "14 lutego"
        single_match = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)(?:\s+(\d{4}))?", clean)
        if single_match:
            d, m_name, y = single_match.groups()
            m_num = MONTHS_PL.get(m_name)
            year = int(y) if y else default_year
            if m_num:
                iso_d = f"{year}-{m_num:02d}-{int(d):02d}"
                return iso_d, iso_d

        # 3. Format DD.MM.YYYY
        dot_match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", clean)
        if dot_match:
            d, m, y = dot_match.groups()
            iso_d = f"{y}-{int(m):02d}-{int(d):02d}"
            return iso_d, iso_d

        # 4. Sam miesiąc: "marzec"
        for m_name, m_num in MONTHS_PL.items():
            if m_name == clean or clean.startswith(m_name):
                # Zakres obejmujący cały miesiąc
                d_end = 31 if m_num in [1, 3, 5, 7, 8, 10, 12] else (30 if m_num != 2 else 28)
                return f"{default_year}-{m_num:02d}-01", f"{default_year}-{m_num:02d}-{d_end:02d}"

        return None, None

    def _scrape_calendar_table(self, today_iso: str, default_year: int) -> List[Dict[str, Any]]:
        events = []
        default_img = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"
        
        try:
            soup = self.get_soup(self.calendar_url)
            rows = soup.select("table tr, .table tr")
            
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue

                term_text = cols[1].get_text(strip=True)
                title_col = cols[2]
                title = re.sub(r"\s+", " ", title_col.get_text()).strip()

                if not title or len(title) < 4 or title.lower() in ["nazwa imprezy", "nr"]:
                    continue

                d_start, d_end = self._parse_term_text(term_text, default_year)
                check_date = d_end or d_start
                if not check_date or check_date < today_iso:
                    continue

                link_el = title_col.select_one("a[href]")
                source_url = urljoin(self.base_url, link_el["href"]) if link_el else urljoin(self.base_url, self.calendar_url)

                venue, address = self._extract_venue_info(title)

                events.append({
                    "title": title,
                    "date_start": d_start,
                    "date_end": d_end,
                    "time_start": "Według harmonogramu",
                    "venue": venue,
                    "address": address,
                    "price_range": "Sprawdź cennik / Wstęp wolny",
                    "description": f"Wydarzenie sportowe MOSiR Kędzierzyn-Koźle: {title}. Termin: {term_text}.",
                    "image_url": default_img,
                    "source_url": source_url,
                    "source": self.source_name,
                    "organizer": "MOSiR Kędzierzyn-Koźle"
                })
        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania tabeli kalendarza: {e}")

        return events

    def _scrape_news_feed(self, today_iso: str, default_year: int) -> List[Dict[str, Any]]:
        events = []
        default_img = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"

        try:
            soup = self.get_soup(self.news_url)
            items = soup.select(".item, article, .article, .blog-item, .news-item, .contentpaneopen")
            if not items:
                items = soup.select(".content .row > div")

            for item in items:
                text = item.get_text(" ", strip=True)
                if any(ignored in text.lower() for ignored in IGNORE_KEYWORDS):
                    continue

                # Szukamy daty w tekście (np. "do 30.08.2026", "28.08.2026")
                d_match = re.search(r"\b([0-3]?[0-9])\.([0-1]?[0-9])\.(20\d{2})\b", text)
                if not d_match:
                    continue

                day, month, year = d_match.groups()
                date_str = f"{year}-{int(month):02d}-{int(day):02d}"

                if date_str < today_iso:
                    continue

                # Wyciąganie tytułu
                title_el = item.select_one("h2, h3, h4, .title, a")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title or len(title) < 5 or title.lower() in ["aktualności", "więcej..."]:
                    # Próba wyciągnięcia pierwszej linijki tekstu
                    first_line = text.split("Zapraszamy")[0].strip()
                    title = first_line[:60] if len(first_line) > 5 else "Wydarzenie MOSiR"

                link_el = item.select_one("a[href]")
                href = link_el.get("href", "") if link_el else ""
                source_url = urljoin(self.base_url, href) if href and not href.startswith("javascript") else urljoin(self.base_url, self.news_url)

                img_el = item.select_one("img[src]")
                raw_image = urljoin(self.base_url, img_el["src"]) if img_el and img_el.get("src") else default_img
                thumb_path = self.save_thumbnail(raw_image, title, prefix="mosirkk") if (raw_image and "unsplash" not in raw_image) else ""

                venue, address = self._extract_venue_info(f"{title} {text}")

                events.append({
                    "title": title,
                    "date_start": date_str,
                    "date_end": date_str,
                    "time_start": "Według harmonogramu",
                    "venue": venue,
                    "address": address,
                    "price_range": "Sprawdź cennik / Wstęp wolny",
                    "description": text[:400],
                    "image_url": thumb_path or raw_image or default_img,
                    "source_url": source_url,
                    "source": self.source_name,
                    "organizer": "MOSiR Kędzierzyn-Koźle"
                })
        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania newsów: {e}")

        return events

    def fetch_events(self) -> List[Dict[str, Any]]:
        today_iso = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().year

        print(f"[{self.source_name}] Skanowanie terminarza i aktualności MOSiR Kędzierzyn-Koźle...")

        cal_events = self._scrape_calendar_table(today_iso, current_year)
        news_events = self._scrape_news_feed(today_iso, current_year)

        # Deduplikacja po source_url i tytule
        all_events = []
        seen = set()

        for ev in cal_events + news_events:
            dedup_key = f"{ev['title'].lower()}_{ev['date_start']}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            all_events.append(ev)

        print(f"[{self.source_name}] Zwrócono {len(all_events)} aktywnych pozycji.")
        return all_events
