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

MONTH_MAP = {
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

CITY_URL_MAP = {
    "kedzierzyn_kozle": "https://biletyna.pl/Kedzierzyn-Kozle",
    "bielsko_biala": "https://biletyna.pl/Bielsko-Biala",
    "opole": "https://biletyna.pl/Opole",
    "gliwice": "https://biletyna.pl/Gliwice",
    "katowice": "https://biletyna.pl/Katowice",
    "wroclaw": "https://biletyna.pl/Wroclaw",
    "krakow": "https://biletyna.pl/Krakow",
}

CITY_NAMES = {
    "kedzierzyn_kozle": "Kędzierzyn-Koźle",
    "bielsko_biala": "Bielsko-Biała",
    "opole": "Opole",
    "gliwice": "Gliwice",
    "katowice": "Katowice",
    "wroclaw": "Wrocław",
    "krakow": "Kraków",
}


class BiletynaPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="biletyna_pl",
            base_url="https://biletyna.pl"
        )
        self.city_tag = city_tag.strip().lower()
        self.partner_id = partner_id
        self.city_name = CITY_NAMES.get(self.city_tag, self.city_tag.replace("_", " ").title())
        self.events_url = CITY_URL_MAP.get(
            self.city_tag,
            f"https://biletyna.pl/szukaj?q={quote_plus(self.city_name)}"
        )

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        })

    def _format_url(self, raw_url: str) -> str:
        clean_url = urljoin(self.base_url, raw_url)
        if self.partner_id:
            separator = "&" if "?" in clean_url else "?"
            return f"{clean_url}{separator}ref={self.partner_id}"
        return clean_url

    def _parse_date(self, text: str) -> str:
        current_year = datetime.now().year

        iso_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", text)
        if iso_match:
            return iso_match.group(1)

        dot_match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(202\d)\b", text)
        if dot_match:
            d, m, y = dot_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        month_pattern = "|".join(MONTH_MAP.keys())
        word_match = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?\b", text, re.IGNORECASE)
        if word_match:
            d, m_name, y = word_match.groups()
            m = MONTH_MAP[m_name.lower()]
            year = int(y) if y else current_year
            if not y and m < datetime.now().month:
                year += 1
            return f"{year}-{m:02d}-{int(d):02d}"

        short_dot = re.search(r"\b(\d{1,2})\.(\d{1,2})\b", text)
        if short_dot:
            d, m = short_dot.groups()
            month_val = int(m)
            if 1 <= month_val <= 12 and 1 <= int(d) <= 31:
                year = current_year if month_val >= datetime.now().month else current_year + 1
                return f"{year}-{month_val:02d}-{int(d):02d}"

        return ""

    def _parse_time(self, text: str) -> str:
        match = re.search(r"godz(?:ina|\.)?\s*([01]?[0-9]|2[0-3])[:.]([0-5][0-9])", text, re.IGNORECASE)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"

        match_simple = re.search(r"\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b", text)
        if match_simple:
            return f"{int(match_simple.group(1)):02d}:{match_simple.group(2)}"

        return "Według harmonogramu"

    def _parse_price(self, text: str) -> str:
        match = re.search(r"(?:od\s*)?(\d+(?:[.,]\d{2})?)\s*(?:zł|PLN)", text, re.IGNORECASE)
        if match:
            return f"Od {match.group(1).replace(',', '.')} zł"
        return "Bilety płatne"

    def _parse_json_ld(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        events = []
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string.strip())
                items = data if isinstance(data, list) else [data]
                if isinstance(data, dict) and "@graph" in data:
                    items = data["@graph"]

                for item in items:
                    if not isinstance(item, dict) or item.get("@type") != "Event":
                        continue

                    title = item.get("name", "").strip()
                    start_date_raw = item.get("startDate", "")
                    if not title or not start_date_raw:
                        continue

                    date_str = start_date_raw[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", start_date_raw) else self._parse_date(start_date_raw)
                    if not date_str:
                        continue

                    time_start = "Według harmonogramu"
                    if "T" in start_date_raw:
                        time_part = start_date_raw.split("T")[1][:5]
                        if re.match(r"^\d{2}:\d{2}$", time_part):
                            time_start = time_part

                    venue = "Obiekt widowiskowy"
                    loc = item.get("location")
                    if isinstance(loc, dict):
                        venue = loc.get("name", venue)
                    elif isinstance(loc, str):
                        venue = loc

                    price_range = "Bilety płatne"
                    offers = item.get("offers")
                    if isinstance(offers, dict):
                        p = offers.get("price") or offers.get("lowPrice")
                        if p:
                            price_range = f"Od {p} zł"
                    elif isinstance(offers, list) and offers:
                        p = offers[0].get("price") or offers[0].get("lowPrice")
                        if p:
                            price_range = f"Od {p} zł"

                    img = item.get("image", "")
                    image_url = img[0] if isinstance(img, list) and img else (img.get("url", "") if isinstance(img, dict) else str(img))

                    thumb_path = self.save_thumbnail(image_url, title, prefix=f"biletyna_{self.city_tag}") if image_url else ""
                    event_url = self._format_url(item.get("url", ""))

                    events.append({
                        "title": title,
                        "date_start": date_str,
                        "date_end": date_str,
                        "time_start": time_start,
                        "venue": venue,
                        "address": f"{venue}, {self.city_name}",
                        "price_range": price_range,
                        "description": item.get("description") or f"Wydarzenie biletowane: {title}. Obiekt: {venue}.",
                        "image_url": thumb_path or image_url,
                        "source_url": event_url,
                        "source": self.source_name,
                        "organizer": "Biletyna.pl"
                    })
            except Exception:
                continue
        return events

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")

        try:
            resp = self.session.get(self.events_url, timeout=(3.05, 10), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code} dla {self.events_url}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")

            ld_events = self._parse_json_ld(soup)
            if ld_events:
                valid_ld = [e for e in ld_events if e["date_start"] >= today_iso]
                print(f"[{self.source_name}] Sparsowano {len(valid_ld)} pozycji z JSON-LD dla '{self.city_tag}'.")
                return valid_ld

            cards = soup.select(".event-box, .single-event, .event-card, .event-item, div[class*='event']")
            seen_urls = set()

            for card in cards:
                link_el = card.select_one(
                    "a[href*='/event/'], a[href*='/spektakl/'], a[href*='/koncert/'], "
                    "a[href*='/film/'], a[href*='/kabaret/'], a[href*='/stand-up/']"
                )
                if not link_el or not link_el.get("href"):
                    continue

                full_url = self._format_url(link_el["href"])
                if full_url in seen_urls:
                    continue

                card_text = card.get_text(" ", strip=True)
                date_str = self._parse_date(card_text)
                if not date_str or date_str < today_iso:
                    continue

                title_el = card.select_one("h2, h3, h4, .title, .event-title, strong")
                title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
                if len(title) < 3 or title.lower() in ["kup bilet", "szczegóły", "więcej"]:
                    continue

                seen_urls.add(full_url)
                time_start = self._parse_time(card_text)
                price_range = self._parse_price(card_text)

                venue = "Obiekt widowiskowy"
                venue_el = card.select_one(".place, .venue, .location, .event-place, a[href*='/miejsce/']")
                if venue_el:
                    venue = venue_el.get_text(strip=True)
                else:
                    v_match = re.search(r"(?:w|–|-)\s+([A-ZŁŚŻŹ0-9][\w\s.\-–]+?)(?:,|\s+godz|\.|$)", card_text)
                    if v_match and 3 < len(v_match.group(1).strip()) < 50:
                        venue = v_match.group(1).strip(" –-.,")

                image_url = ""
                img_el = card.select_one("img[src], img[data-src]")
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src", "")
                    if not src.startswith("data:"):
                        image_url = urljoin(self.base_url, src)

                thumb_path = self.save_thumbnail(image_url, title, prefix=f"biletyna_{self.city_tag}") if image_url else ""

                events.append({
                    "title": title,
                    "date_start": date_str,
                    "date_end": date_str,
                    "time_start": time_start,
                    "venue": venue,
                    "address": f"{venue}, {self.city_name}",
                    "price_range": price_range,
                    "description": f"Wydarzenie biletowane: {title}. Miejsce: {venue}.",
                    "image_url": thumb_path or image_url,
                    "source_url": full_url,
                    "source": self.source_name,
                    "organizer": "Biletyna.pl"
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd przetwarzania: {e}")

        print(f"[{self.source_name}] Sparsowano {len(events)} wydarzeń dla '{self.city_tag}'.")
        return events
