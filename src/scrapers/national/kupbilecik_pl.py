from datetime import datetime
import json
import re
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup
import requests

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


class KupBilecikPlScraper:
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        self.city_tag = city_tag
        self.partner_id = partner_id
        self.source_name = f"kupbilecik_{city_tag}"
        self.base_url = "https://www.kupbilecik.pl"
        self.city_query = CITY_SEARCH_QUERIES.get(city_tag, city_tag.replace("_", " ").title())
        self.city_patterns = CITY_MATCH_PATTERNS.get(city_tag, [city_tag.replace("_", "")])
        
        # Zapytanie do wyszukiwarki serwisu
        self.events_url = f"https://www.kupbilecik.pl/szukaj/?q={quote_plus(self.city_query)}"

        self.session = requests.Session()
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

    def _is_matching_city(self, text: str) -> bool:
        norm = text.lower()
        return any(pattern in norm for pattern in self.city_patterns)

    def _parse_date(self, text: str) -> str:
        current_year = datetime.now().year

        # 1. DD [miesiąc słownie] YYYY
        month_pattern = "|".join(MONTH_MAP.keys())
        word_match = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?\b", text, re.IGNORECASE)
        if word_match:
            d, m_name, y = word_match.groups()
            m = MONTH_MAP[m_name.lower()]
            year = int(y) if y else current_year
            if not y and m < datetime.now().month:
                year += 1
            return f"{year}-{m:02d}-{int(d):02d}"

        # 2. DD.MM.YYYY
        dot_match = re.search(r"\b(\d{{1,2}})\.(\d{{1,2}})\.(\d{{4}})\b", text)
        if dot_match:
            d, m, y = dot_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # 3. YYYY-MM-DD
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

    def fetch_events(self) -> list[dict]:
        events = []
        try:
            resp = self.session.get(self.events_url, timeout=15)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")
            seen_urls = set()

            # Szukamy linków do zakupu biletu lub podstron imprez
            event_links = soup.select("a[href*='/imprezy/'], a[href*='/wydarzenia/'], a[href*='/bilet/']")

            for a_tag in event_links:
                href = a_tag.get("href", "")
                if not href or not re.search(r"/(?:imprezy|wydarzenia)/\d+/", href):
                    continue

                full_url = self._format_url(href)
                if full_url in seen_urls:
                    continue

                # Wspinaczka do wiersza wynikowego tabeli
                row = a_tag
                for _ in range(5):
                    parent = row.parent
                    if not parent or parent.name in ["body", "html", "main"]:
                        break
                    row = parent
                    if "Kup bilet" in row.get_text() and ("godz" in row.get_text() or re.search(r"\d{1,2}\s+[a-ząćęłńóśźż]{3,}", row.get_text())):
                        break

                row_text = row.get_text(" ", strip=True)

                # Weryfikacja czy wiersz dotyczy szukanego miasta
                if not self._is_matching_city(row_text):
                    continue

                # Parsowanie daty
                date_str = self._parse_date(row_text)
                if not date_str:
                    continue

                # Parsowanie tytułu
                title = ""
                # Szukamy linku z nazwą wydarzenia (innego niż przycisk "Kup bilet")
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

                # Parsowanie sali / obiektu (np. Hotel Hugo, Klub Kameleon, Hala Sportowa Śródmieście)
                venue = "Obiekt widowiskowy"
                venue_el = row.select_one("a[href*='/obiekty/']")
                if venue_el:
                    venue = venue_el.get_text(strip=True)
                else:
                    # Szukanie nazwy obiektu występującej po nazwie miasta w wierszu
                    m_loc = re.search(rf"(?:{self.city_query}|Koźle)\s*[\n\r,·-]?\s*([A-ZŁŚŻŹ0-9][\w\s.\-–]+?)(?:Kup bilet|Od\s*\d|\d+\s*zł|$)", row_text)
                    if m_loc and 2 < len(m_loc.group(1).strip()) < 50:
                        venue = m_loc.group(1).strip(" –-.,")

                # Parsowanie zdjęcia
                image_url = ""
                img_el = row.select_one("img[src], img[data-src]")
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src", "")
                    if not src.startswith("data:"):
                        image_url = urljoin(self.base_url, src)

                events.append({
                    "title": title,
                    "date": date_str,
                    "time_start": time_start,
                    "venue": venue,
                    "address": f"{venue}, {self.city_query}",
                    "price_range": "Bilety płatne",
                    "description": f"Wydarzenie biletowane: {title}. Miejsce: {venue}.",
                    "image_url": image_url,
                    "url": full_url,
                    "source": "kupbilecik_pl",
                    "organizer": "KupBilecik.pl"
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania: {e}")

        return events


if __name__ == "__main__":
    import sys
    test_city = sys.argv[1] if len(sys.argv) > 1 else "kedzierzyn_kozle"
    scraper = KupBilecikPlScraper(city_tag=test_city)
    data = scraper.fetch_events()
    print(f"\n[{test_city.upper()}] Pobrano wydarzeń: {len(data)}\n")
    print(json.dumps(data, indent=2, ensure_ascii=False))