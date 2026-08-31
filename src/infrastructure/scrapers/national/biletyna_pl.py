import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CITY_URL_MAP = {
    "kedzierzyn_kozle": "https://biletyna.pl/Kedzierzyn-Kozle",
    "bielsko_biala": "https://biletyna.pl/Bielsko-Biala",
    "opole": "https://biletyna.pl/Opole"
}

CITY_NAMES = {
    "kedzierzyn_kozle": "Kędzierzyn-Koźle",
    "bielsko_biala": "Bielsko-Biała",
    "opole": "Opole"
}

class BiletynaPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(source_name="biletyna_pl", base_url="https://biletyna.pl")
        self.city_tag = city_tag.strip().lower()
        self.partner_id = partner_id
        self.city_name = CITY_NAMES.get(self.city_tag, self.city_tag.replace("_", " ").title())
        self.events_url = CITY_URL_MAP.get(self.city_tag, f"https://biletyna.pl/szukaj?q={quote_plus(self.city_name)}")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })

    def _format_url(self, raw_url: str) -> str:
        clean = urljoin(self.base_url, raw_url)
        return f"{clean}{'&' if '?' in clean else '?'}ref={self.partner_id}" if self.partner_id else clean

    def _clean_seo_title(self, title: str) -> str:
        if not title: return "Wydarzenie"
        title = re.split(r'\s*\|\s*(Bilety|Opis|Recenzje|Kup|202)', title, flags=re.IGNORECASE)[0]
        title = re.split(r'\s*-\s*(Bilety|Kup|Rezerwuj)', title, flags=re.IGNORECASE)[0]
        return title.strip()

    def _parse_row_event(self, row: BeautifulSoup, full_desc: str, full_img: str, global_title: str, global_venue: str, event_url: str, row_idx: int = 1, total_rows: int = 1) -> Optional[Dict[str, Any]]:
        row_text = row.get_text(" ", strip=True)
        row_text_clean = re.sub(r'\s+', ' ', row_text)
        
        date_match = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", row_text_clean)
        if not date_match: return None
        d, m, y = date_match.groups()
        date_iso = f"{y}-{m}-{d}"
        if date_iso < datetime.now().strftime("%Y-%m-%d"): return None

        time_match = re.search(r"\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b", row_text_clean)
        time_str = f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else "Według harmonogramu"

        title_el = row.select_one("h2, h3, h4, strong")
        title = self._clean_seo_title(title_el.get_text(strip=True)) if title_el else global_title
        if title.lower() in [self.city_name.lower(), self.city_tag.lower(), "wydarzenie"]:
            title = global_title

        # NOWA LOGIKA WYCIĄGANIA MIEJSCA - Odporna na brak klas CSS i nowy layout biletowy
        venue = ""
        venue_el = row.select_one("a[href*='/miejsce/']")
        if venue_el:
            venue = venue_el.get_text(strip=True)
        else:
            # Wycina tekst zlokalizowany pomiędzy nazwą miasta a statusem biletów
            v_match = re.search(rf"{re.escape(self.city_name)}\s+(.*?)\s+(?:Dostępne|Bilety\s+od|KUP|Wyprzedane|Szczegóły)", row_text_clean, re.IGNORECASE)
            if v_match:
                venue = v_match.group(1).strip()
            
            if not venue:
                venue = global_venue

        if len(venue) > 50 or venue.lower() == self.city_name.lower():
            venue = ""

        price_match = re.search(r"(?:Bilety\s+od|od)\s*(\d+(?:[.,]\d{2})?)\s*(?:zł|PLN)", row_text_clean, re.IGNORECASE)
        price_str = f"Od {price_match.group(1).replace(',', '.')} zł" if price_match else "Bilety płatne"

        thumb_path = self.save_thumbnail(full_img, title, prefix=f"biletyna_{self.city_tag}") if full_img else ""
        desc = re.sub(r'\s+', ' ', full_desc).strip() if full_desc else f"{title}. Czas: {date_iso} {time_str}. Miejsce: {venue or 'Przestrzeń miejska'}."

        return {
            "title": title,
            "date_start": date_iso,
            "time_start": time_str,
            "venue": venue,
            "address": f"{venue}, {self.city_name}".strip(", "),
            "price_range": price_str,
            "description": desc,
            "image_url": thumb_path or full_img,
            "source_url": f"{event_url}#{row_idx}" if total_rows > 1 else event_url,
            "source": self.source_name,
            "organizer": "Biletyna.pl",
            "city_tag": self.city_tag
        }

    def _scrape_detail_page(self, event_url: str, fallback_title: str) -> List[Dict[str, Any]]:
        page_events = []
        try:
            resp = self.session.get(event_url, timeout=(3.05, 10), verify=False)
            if resp.status_code != 200: return page_events
            soup = BeautifulSoup(resp.text, "html.parser")

            h1_el = soup.select_one("h1")
            global_title = self._clean_seo_title(h1_el.get_text(strip=True)) if h1_el else self._clean_seo_title(fallback_title)
            
            global_desc = ""
            global_img = ""
            global_venue = ""

            for s in soup.find_all("script", type="application/ld+json"):
                if not s.string: continue
                try:
                    schema = json.loads(s.string.strip())
                    items = schema if isinstance(schema, list) else [schema]
                    for item in items:
                        if isinstance(item, dict):
                            desc = item.get("description")
                            if desc and len(desc) > len(global_desc): global_desc = desc.strip()
                            
                            img = item.get("image")
                            if img and not global_img:
                                global_img = img if isinstance(img, str) else (img[0] if isinstance(img, list) else img.get("url", ""))
                            
                            loc = item.get("location")
                            if isinstance(loc, list) and loc: loc = loc[0]
                            if isinstance(loc, dict):
                                loc_name = loc.get("name")
                                if loc_name and len(loc_name) < 50:
                                    global_venue = loc_name
                except Exception:
                    pass

            if not global_desc:
                desc_el = soup.select_one(".event-description, .desc, .description, #description, .event-details")
                if desc_el: global_desc = desc_el.get_text("\n", strip=True)

            if not global_img:
                img_el = soup.select_one(".event-image img, meta[property='og:image']")
                if img_el: global_img = img_el.get("content") or img_el.get("src") or ""

            event_rows = soup.select("tr.event-row, .event-row, .single-event, .event-list-item")
            for idx, row in enumerate(event_rows, 1):
                ev = self._parse_row_event(row, global_desc, global_img, global_title, global_venue, event_url, row_idx=idx, total_rows=len(event_rows))
                if ev: page_events.append(ev)

        except Exception as e:
            pass
        return page_events

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        try:
            resp = self.session.get(self.events_url, timeout=(3.05, 10), verify=False)
            if resp.status_code != 200: return events
            soup = BeautifulSoup(resp.text, "html.parser")
            
            event_links = soup.select("a[href*='/event/'], a[href*='/spektakl/'], a[href*='/koncert/']")
            seen_urls = set()
            urls_to_scrape = []

            for link in event_links:
                href = link.get("href", "").strip()
                if not href or href in ["#", "/"]: continue
                full_url = self._format_url(href)
                if full_url not in seen_urls and not full_url.endswith(("/Bielsko-Biala", "/Kedzierzyn-Kozle")):
                    seen_urls.add(full_url)
                    urls_to_scrape.append((full_url, link.get_text(strip=True)))

            print(f"[{self.source_name}] Pobieranie detali dla {len(urls_to_scrape)} wydarzeń...")
            for full_url, fallback_title in urls_to_scrape:
                events.extend(self._scrape_detail_page(full_url, fallback_title))
        except Exception as e:
            print(f"[{self.source_name}] Błąd głównego parsera: {e}")
            
        print(f"[{self.source_name}] Zakończono dla '{self.city_tag}'. Zebrano {len(events)}.")
        return events
