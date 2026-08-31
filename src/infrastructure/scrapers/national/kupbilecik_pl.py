import re
import urllib.parse
import urllib3
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, unquote
from bs4 import BeautifulSoup
from src.infrastructure.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

POLISH_MONTHS = {
    "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
    "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
    "września": "09", "października": "10", "listopada": "11", "grudnia": "12"
}

class KupBilecikPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(source_name="kupbilecik_pl", base_url="https://www.kupbilecik.pl")
        self.city_tag = city_tag.strip().lower()
        self.partner_id = partner_id

        if "kedzierzyn" in self.city_tag:
            self.search_query = "Kędzierzyn"
            self.canonical_city = "Kędzierzyn-Koźle"
            self.required_slugs = ["kędzierzyn", "kedzierzyn"]
        elif "bielsko" in self.city_tag:
            self.search_query = "Bielsko-Biała"
            self.canonical_city = "Bielsko-Biała"
            self.required_slugs = ["bielsko"]
        elif "opole" in self.city_tag:
            self.search_query = "Opole"
            self.canonical_city = "Opole"
            self.required_slugs = ["opole"]
        else:
            self.search_query = self.city_tag.replace("_", " ")
            self.canonical_city = self.city_tag.replace("_", " ").title()
            self.required_slugs = [self.city_tag.replace("_", " ")]

        self.events_url = f"{self.base_url}/szukaj/?q={quote_plus(self.search_query)}"

    def _format_url(self, raw_url: str) -> str:
        clean_url = urljoin(self.base_url, raw_url)
        if self.partner_id:
            sep = "&" if "?" in clean_url else "?"
            return f"{clean_url}{sep}pv={self.partner_id}"
        return clean_url

    def _parse_date(self, text: str) -> str:
        match = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", text, re.IGNORECASE)
        if match:
            day, month_name, year = match.groups()
            month = POLISH_MONTHS.get(month_name.lower(), "01")
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return ""

    def _parse_time(self, text: str) -> str:
        match = re.search(r"godz\.?\s*(\d{1,2}[:.]\d{2})", text, re.IGNORECASE)
        if match:
            return match.group(1).replace(".", ":")
        return ""

    def _scrape_detail_page(self, event_url: str, fallback_title: str, fb_date: str, fb_time: str, fb_venue: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.session.get(
                event_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=(3.05, 10),
                verify=False
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            
            h1_el = soup.select_one("h1")
            title = h1_el.get_text(strip=True) if h1_el else fallback_title
            title = re.sub(r"(?i)\s*-\s*(bilety|kup|rezerwuj).*$", "", title).strip()

            date_iso = fb_date
            time_str = fb_time
            venue = ""
            street = ""

            # PRECYZYJNE SZUKANIE W ZAMKNIĘTYM KONTENERZE (Izolacja od okruszków nawigacyjnych)
            info_block = soup.select_one(".wyd-date-table, .wyd-date-cell, .box-wyd-dane")
            if info_block:
                obj_link = info_block.select_one("a[href*='/obiekty/'], a[href*='/miejsce/'], a[href*='/lokalizacja/']")
                if obj_link:
                    venue = obj_link.get_text(strip=True)
                    parent_text = obj_link.parent.get_text(" ", strip=True)
                    street = parent_text.replace(venue, "").replace(self.canonical_city, "").strip(" -,")
                elif info_block.select_one(".line-3"):
                    v_text = info_block.select_one(".line-3").get_text(" ", strip=True)
                    if "," in v_text:
                        venue = v_text.split(",")[0].strip()
                        street = v_text.split(",", 1)[1].strip()
                    else:
                        venue = v_text
                else:
                    strings = list(info_block.stripped_strings)
                    for i, s in enumerate(strings):
                        if "woj." in s or self.canonical_city in s:
                            if i + 1 < len(strings):
                                nxt = strings[i+1]
                                if "godz" not in nxt and "202" not in nxt:
                                    if "," in nxt:
                                        venue = nxt.split(",")[0].strip()
                                        street = nxt.split(",", 1)[1].strip()
                                    else:
                                        venue = nxt
                                break

            # TWARDY BEZPIECZNIK LOGICZNY: Oczyszczony z interpunkcji
            v_clean = re.sub(r'[\W_]+', '', venue.lower()) if venue else ""
            t_clean = re.sub(r'[\W_]+', '', title.lower())
            
            if v_clean and (v_clean in t_clean or t_clean in v_clean):
                venue = fb_venue
                street = ""

            if not venue:
                venue = fb_venue

            if not date_iso:
                body_text = soup.get_text(" ", strip=True)
                d_match = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", body_text, re.IGNORECASE)
                if d_match: date_iso = self._parse_date(d_match.group(0))
                t_match = re.search(r"godz\.?\s*(\d{1,2}[:.]\d{2})", body_text, re.IGNORECASE)
                if t_match: time_str = t_match.group(1).replace(".", ":")

            if not date_iso:
                return None

            venue = re.sub(r"(?i)\bobiekt widowiskowy\b", "", venue).strip()
            for slug in self.required_slugs:
                venue = re.sub(rf"(?i)\b{re.escape(slug)}\b", "", venue).replace("-", "").strip(" ,wW")
            
            if not venue or len(venue) < 3:
                venue = self.canonical_city

            if street:
                address = f"{venue}, {street}, {self.canonical_city}".replace(" ,", ",").strip(", ")
            else:
                address = f"{venue}, {self.canonical_city}".strip(", ")

            image_url = ""
            og_img = soup.select_one("meta[property='og:image'], meta[name='twitter:image']")
            if og_img and og_img.get("content"):
                image_url = urljoin(self.base_url, og_img.get("content").strip())
            
            if not image_url:
                img_el = soup.select_one("img[src*='/plakaty/'], img[src*='/zdjecia/'], img[src*='/i/'], img[src*='/upload/'], .wyd-img img, .top-image img")
                if img_el:
                    src = img_el.get("src") or img_el.get("data-src")
                    if src: image_url = urljoin(self.base_url, src)

            thumb_path = self.save_thumbnail(image_url, title, prefix=f"kupbilecik_{self.city_tag}") if image_url else ""
            unique_url = f"{event_url}#{date_iso}-{time_str.replace(':', '')}"

            return {
                "title": title,
                "date_start": date_iso,
                "time_start": time_str,
                "venue": venue,
                "address": address,
                "image_url": thumb_path or image_url,
                "source_url": unique_url,
                "organizer": "KupBilecik",
                "source": self.source_name,
                "city_tag": self.city_tag
            }

        except Exception as e:
            print(f"[{self.source_name}] Błąd podstrony {event_url}: {e}")
            return None

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        try:
            resp = self.session.get(
                self.events_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=(3.05, 10),
                verify=False
            )
            if resp.status_code != 200:
                return events

            soup = BeautifulSoup(resp.text, "html.parser")
            seen_urls = set()
            urls_to_scrape = []

            for card in soup.select(".wyd-szukaj-table, .row-cell"):
                link = card.select_one("a[href*='/imprezy/']")
                if not link: continue
                
                href = link.get("href", "").strip()
                if not href or href in ["#", "/"]: continue
                
                full_url = self._format_url(href)
                norm_url = unquote(full_url).lower()
                if not any(slug in norm_url for slug in self.required_slugs): continue
                if 'opole' in self.city_tag and 'lubelskie' in norm_url: continue

                title_fallback = link.get_text(strip=True)
                if not title_fallback or title_fallback.lower() in ["informacje", "kup bilet", "bilety"]: continue

                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    
                    fb_date = ""
                    fb_time = ""
                    fb_venue = ""
                    
                    card_text = card.get_text(" ", strip=True)
                    fb_date = self._parse_date(card_text)
                    fb_time = self._parse_time(card_text)
                    
                    v_el = card.select_one(".cell-wyd-lista-4, .linia-4")
                    if v_el:
                        fb_venue = v_el.get_text(" ", strip=True)
                        fb_venue = re.sub(rf"(?i){self.canonical_city}\s*w\s*", "", fb_venue)
                        fb_venue = re.sub(r"(?i)\bw\b\s*", "", fb_venue)
                        for slug in self.required_slugs:
                            fb_venue = re.sub(rf"(?i)\b{re.escape(slug)}\b", "", fb_venue)
                        fb_venue = fb_venue.strip(" ,-wW")

                    urls_to_scrape.append((full_url, title_fallback, fb_date, fb_time, fb_venue))

            print(f"[{self.source_name}] Pobieranie szczegółów dla {len(urls_to_scrape)} stron wydarzeń...")
            for full_url, title_fallback, fb_date, fb_time, fb_venue in urls_to_scrape:
                ev = self._scrape_detail_page(full_url, title_fallback, fb_date, fb_time, fb_venue)
                if ev:
                    events.append(ev)

        except Exception as e:
            print(f"[{self.source_name}] Błąd głównego parsera: {e}")

        print(f"[{self.source_name}] Zakończono. Pobrano {len(events)} zweryfikowanych wydarzeń.")
        return events
