from datetime import datetime
import os
import re
import sys
from typing import Any, Dict, List, Set
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.infrastructure.scrapers.base import BaseScraper

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

TAXONOMY_DISCOUNTS = {
    "17": {"name": "Karta Weteran +", "val": "-50%"},
    "18": {"name": "Bielska Karta Rodzina +", "val": "-50%"},
    "19": {"name": "Bielska Karta SENIORA", "val": "-50%"},
    "42": {"name": "legitymacja ZASŁUŻONY DLA ZDROWIA NARODU", "val": "-50%"}
}


class BckBielskoPlScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="bck_bielsko_pl",
            base_url="https://www.bck.bielsko.pl"
        )
        self.repertoire_url = f"{self.base_url}/repertuar"
        self.seen_signatures: Set[str] = set()

    def _parse_datetime(self, meta_text: str, card: BeautifulSoup) -> tuple:
        now = datetime.now()
        time_str = "18:00"
        m_time = re.search(r"godz\.\s*([01]?[0-9]|2[0-3])[:.]([0-5][0-9])", meta_text, re.IGNORECASE)
        if m_time:
            time_str = f"{int(m_time.group(1)):02d}:{m_time.group(2)}"

        month_pattern = "|".join(POLISH_MONTH_MAP.keys())
        m_date = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?", meta_text, re.IGNORECASE)
        if m_date:
            d, m_name, y = m_date.groups()
            m_num = POLISH_MONTH_MAP[m_name.lower()]
            if y:
                year_val = int(y)
            else:
                year_val = now.year if m_num >= now.month else now.year + 1
            return f"{year_val}-{m_num:02d}-{int(d):02d}", time_str

        date_el = card.select_one(".event-date")
        if date_el:
            day_txt = date_el.select_one(".date")
            month_txt = date_el.select_one(".month")
            if day_txt and month_txt:
                d_val = re.search(r"\d+", day_txt.get_text(strip=True))
                m_word = month_txt.get_text(strip=True).lower()
                if d_val and m_word in POLISH_MONTH_MAP:
                    m_num = POLISH_MONTH_MAP[m_word]
                    year_val = now.year if m_num >= now.month else now.year + 1
                    return f"{year_val}-{m_num:02d}-{int(d_val.group()):02d}", time_str

        return "", time_str

    def _fetch_event_discounts(self, event_url: str) -> List[Dict[str, str]]:
        if not event_url or event_url == self.repertoire_url:
            return []
        try:
            resp = self.session.get(event_url, timeout=(3.05, 7))
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.content, "html.parser")
            found = []
            for term_id, disc in TAXONOMY_DISCOUNTS.items():
                if soup.find("a", href=re.compile(rf"/taxonomy/term/{term_id}(?:/|\b|$)")):
                    found.append(disc)
            return found
        except Exception:
            return []

    def fetch_events(self) -> List[Dict[str, Any]]:
        raw_cards = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie repertuaru Bielskiego Centrum Kultury...")

        for page_idx in range(6):
            page_url = f"{self.repertoire_url}?page={page_idx}" if page_idx > 0 else self.repertoire_url
            try:
                resp = self.session.get(page_url, timeout=(3.05, 10))
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.content, "html.parser")
                cards = soup.select(".event-block-2")
                if not cards:
                    break

                for card in cards:
                    title_el = card.select_one("h3 a, h3")
                    if not title_el:
                        continue

                    title = re.sub(r"\s+", " ", title_el.get_text(strip=True)).strip()
                    if len(title) < 3:
                        continue

                    event_url = urljoin(self.base_url, title_el.get("href", "")) if (title_el.name == "a" or title_el.has_attr("href")) else self.repertoire_url
                    link_el = card.select_one("h3 a, .item-image a")
                    if link_el and link_el.get("href"):
                        event_url = urljoin(self.base_url, link_el["href"])

                    meta_el = card.select_one(".event-meta")
                    meta_text = meta_el.get_text(" ", strip=True) if meta_el else ""
                    date_iso, time_str = self._parse_datetime(meta_text, card)

                    if not date_iso or date_iso < today_iso:
                        continue

                    sig = f"{date_iso}_{time_str}_{title.lower()}"
                    if sig in self.seen_signatures:
                        continue
                    self.seen_signatures.add(sig)

                    img_el = card.select_one(".item-image img, img")
                    remote_img_url = img_el.get("src", "") if img_el else ""
                    full_remote_img = urljoin(self.base_url, remote_img_url) if remote_img_url else ""
                    thumbnail_path = self.save_thumbnail(full_remote_img, title, prefix="bck")

                    price_info = "Bilety płatne"
                    btn_el = card.select_one(".aktualbtn, .btn-theme, a[href*='bilety']")
                    if btn_el:
                        btn_text = btn_el.get_text(strip=True)
                        if "wolny" in btn_text.lower() or "bezpłat" in btn_text.lower():
                            price_info = "Wstęp wolny"
                        elif "bilet" in btn_text.lower():
                            price_info = "Bilety płatne"
                        elif len(btn_text) > 2:
                            price_info = btn_text

                    desc_el = card.select_one(".event-description, .field--name-field-skrot")
                    description = desc_el.get_text("\n\n", strip=True) if desc_el else f"Wydarzenie w Bielskim Centrum Kultury: {title}."
                    description = re.sub(r"\s+", " ", description).strip()

                    raw_cards.append({
                        "title": title,
                        "date_start": date_iso,
                        "date_end": date_iso,
                        "time_start": time_str,
                        "venue": "Bielskie Centrum Kultury im. Marii Koterbskiej",
                        "address": "ul. Juliusza Słowackiego 27, Bielsko-Biała",
                        "price_range": price_info,
                        "description": description,
                        "image_url": thumbnail_path or full_remote_img,
                        "source_url": event_url,
                        "source": self.source_name,
                        "organizer": "Bielskie Centrum Kultury"
                    })

            except Exception as e:
                print(f"[{self.source_name}] Błąd parsowania strony {page_idx}: {e}")

        print(f"[{self.source_name}] Skanowanie taksonomii zniżek dla {len(raw_cards)} wydarzeń...")
        events = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_ev = {executor.submit(self._fetch_event_discounts, ev["source_url"]): ev for ev in raw_cards}
            for future in as_completed(future_to_ev):
                ev = future_to_ev[future]
                try:
                    discs = future.result()
                except Exception:
                    discs = []
                
                ev["ticket_offers"] = [{
                    "provider": "Organizator",
                    "url": ev["source_url"],
                    "price": ev["price_range"],
                    "is_primary": True,
                    "discounts": discs
                }]
                events.append(ev)

        print(f"[{self.source_name}] Pomyślnie sparsowano {len(events)} wydarzeń BCK.")
        return events
