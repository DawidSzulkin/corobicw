import concurrent.futures
import html
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

GENRES = {"muzyka", "kabaret", "teatr", "stand-up", "sport", "dla dzieci", "inne", "komedia", "koncert", "widowisko"}
VENUE_KEYWORDS = ["dom kultury", "bck", "mok", "mdk", "hala", "teatr", "filharmonia", "amfiteatr", "scena", "klub", "centrum kultury", "opera"]

class KupBilecikPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(source_name="kupbilecik_pl", base_url="https://www.kupbilecik.pl")
        self.city_tag = city_tag.strip().lower()
        self.partner_id = partner_id

        if "kedzierzyn" in self.city_tag:
            self.search_query = "Kedzierzyn"
            self.canonical_city = "Kędzierzyn-Koźle"
            self.city_tokens = {"kędzierzyn", "kedzierzyn", "koźle", "kozle", "kędzierzyn-koźle", "kedzierzyn-kozle", "śródmieście"}
            self.required_slugs = ["kędzierzyn", "kedzierzyn", "kozle", "koźle"]
        elif "bielsko" in self.city_tag:
            self.search_query = "Bielsko"
            self.canonical_city = "Bielsko-Biała"
            self.city_tokens = {"bielsko", "biała", "biala", "bielsko-biała", "bielsko-biala"}
            self.required_slugs = ["bielsko"]
        elif "opole" in self.city_tag:
            self.search_query = "Opole"
            self.canonical_city = "Opole"
            self.city_tokens = {"opole"}
            self.required_slugs = ["opole"]
        else:
            clean = self.city_tag.replace("_", " ")
            self.search_query = clean
            self.canonical_city = clean.title()
            self.city_tokens = {clean.lower()}
            self.required_slugs = [clean.lower()]

        self.events_url = f"{self.base_url}/pl/search?q={quote_plus(self.search_query)}"

    def _format_url(self, raw_url: str) -> str:
        clean_url = urljoin(self.base_url, raw_url)
        if self.partner_id:
            sep = "&" if "?" in clean_url else "?"
            return f"{clean_url}{sep}pv={self.partner_id}"
        return clean_url

    def _parse_date(self, text: str) -> str:
        m_dot = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if m_dot:
            day, month, year = m_dot.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
            
        m_word = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", text, re.IGNORECASE)
        if m_word:
            day, month_name, year = m_word.groups()
            month = POLISH_MONTHS.get(month_name.lower(), "01")
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return ""

    def _parse_time(self, text: str) -> str:
        match = re.search(r"(?:godz\.?\s*|\b)(\d{1,2}[:.]\d{2})\b", text, re.IGNORECASE)
        if match:
            return match.group(1).replace(".", ":")
        return "19:00"

    def _extract_venue_from_text(self, text: str, title: str) -> str:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        title_lower = title.strip().lower()
        candidates = []

        for p in parts:
            p_clean = p.strip(" ,-–")
            p_lower = p_clean.lower()
            
            if not p_clean or len(p_clean) < 3:
                continue
            if re.search(r"\d{4}", p_clean) or re.search(r"\d{1,2}:\d{2}", p_clean) or "zł" in p_lower:
                continue
            if any(ign in p_lower for ign in ["kup bilet", "bilety", "szczegóły", "zobacz", "rezerwuj"]):
                continue
            if p_lower in GENRES or p_lower in self.city_tokens:
                continue
            if p_lower == title_lower or p_lower in title_lower or title_lower in p_lower:
                continue
            candidates.append(p_clean)

        for c in candidates:
            c_lower = c.lower()
            if any(k in c_lower for k in VENUE_KEYWORDS):
                return c

        if candidates:
            return candidates[0]
            
        return self.canonical_city

    def _scrape_detail_page(self, item_tuple: tuple) -> Optional[Dict[str, Any]]:
        event_url, fallback_title, fb_date, fb_time, fb_venue, raw_card_text = item_tuple
        
        title = fallback_title
        date_iso = fb_date
        time_str = fb_time
        venue = fb_venue or self.canonical_city
        address = f"{venue}, {self.canonical_city}"
        description = f"Wydarzenie: {title}. Miejsce: {venue}, {self.canonical_city}. Bilety dostępne online na KupBilecik.pl."
        price_info = "Bilety płatne (KupBilecik)"
        image_url = ""

        try:
            resp = self.session.get(
                event_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=(3.05, 6.0)
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser")
                
                h1_el = soup.select_one("h1")
                if h1_el:
                    title = re.sub(r"(?i)\s*-\s*(bilety|kup|rezerwuj).*$", "", h1_el.get_text(strip=True)).strip()

                venue_link = soup.select_one("a[href*='/obiekty/'], a[href*='/miejsce/'], [itemprop='location']")
                if venue_link:
                    v_extracted = venue_link.get_text(strip=True)
                    if v_extracted and v_extracted.lower() not in self.city_tokens:
                        venue = v_extracted

                desc_container = soup.select_one(".box-tresc, .wyd-tresc, .wyd-opis, article, .description-content")
                if desc_container:
                    for ext in desc_container.select("script, style"):
                        ext.decompose()
                    raw_text = desc_container.get_text(separator=chr(10), strip=True)
                    desc_parts = [l.strip() for l in raw_text.split(chr(10)) if l.strip() and not any(ign in l.lower() for ign in ["regulamin", "cookies", "kup bilet"])]
                    if desc_parts:
                        description = (chr(10) + chr(10)).join(desc_parts)

                og_img = soup.select_one("meta[property='og:image'], meta[name='twitter:image']")
                if og_img and og_img.get("content"):
                    image_url = urljoin(self.base_url, og_img.get("content").strip())

                price_match = re.search(r"(?:od\s*)?(\d{2,3}(?:[.,]\d{2})?\s*zł)", soup.get_text())
                if price_match:
                    price_info = f"Od {price_match.group(1)}"
        except Exception:
            pass

        if not date_iso:
            return None

        thumb_path = self.save_thumbnail(image_url, title, prefix=f"kupbilecik_{self.city_tag}") if image_url else ""
        unique_url = f"{event_url}#{date_iso}-{time_str.replace(':', '')}"

        return {
            "title": title,
            "date_start": date_iso,
            "date_end": date_iso,
            "time_start": time_str,
            "venue": venue,
            "address": f"{venue}, {self.canonical_city}",
            "price_range": price_info,
            "description": description,
            "image_url": thumb_path or image_url,
            "source_url": unique_url,
            "organizer": "KupBilecik",
            "source": self.source_name,
            "category": "Kultura i Rozrywka",
            "city_tag": self.city_tag
        }

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        try:
            resp = self.session.get(
                self.events_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=(5.0, 12.0)
            )
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code} dla {self.events_url}")
                return events

            soup = BeautifulSoup(resp.content, "html.parser")
            seen_urls = set()
            urls_to_scrape = []

            candidate_links = [a for a in soup.find_all("a", href=True) if re.search(r"/(imprezy|wydarzenia|event)/", a["href"])]

            for a in candidate_links:
                href = a.get("href", "").strip()
                title = a.get_text(strip=True)
                if not href or not title or len(title) < 3:
                    continue
                if title.lower() in ["bilety", "kup bilet", "szczegóły", "informacje"]:
                    continue

                full_url = self._format_url(href)
                norm_url = unquote(full_url).lower()
                if not any(slug in norm_url for slug in self.required_slugs):
                    continue
                if "opole" in self.city_tag and "lubelskie" in norm_url:
                    continue

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                container = a
                while container.parent:
                    parent = container.parent
                    event_links_in_parent = [link for link in parent.find_all("a", href=True) if re.search(r"/(imprezy|wydarzenia|event)/", link["href"])]
                    distinct_targets = {l.get("href") for l in event_links_in_parent}
                    if len(distinct_targets) > 1:
                        break
                    container = parent
                    if container.name in ["body", "html"]:
                        break

                card_text = container.get_text(" | ", strip=True)
                fb_date = self._parse_date(card_text)
                fb_time = self._parse_time(card_text)
                fb_venue = self._extract_venue_from_text(card_text, title)

                urls_to_scrape.append((full_url, title, fb_date, fb_time, fb_venue, card_text))

            print(f"[{self.source_name}] Zlokalizowano {len(urls_to_scrape)} kart ({self.city_tag}). Pobieranie szczegółów...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                results = executor.map(self._scrape_detail_page, urls_to_scrape)
                for ev in results:
                    if ev:
                        events.append(ev)
        except Exception as e:
            print(f"[{self.source_name}] Błąd parsera: {e}")

        print(f"[{self.source_name}] Zakończono dla '{self.city_tag}'. Pobrano {len(events)} wydarzeń.")
        return events
