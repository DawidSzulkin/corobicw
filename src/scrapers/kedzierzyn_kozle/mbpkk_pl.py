import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

POLISH_MONTH_MAP = {
    "stycznia": 1, "styczeń": 1,
    "lutego": 2, "luty": 2,
    "marca": 3, "marzec": 3,
    "kwietnia": 4, "kwiecień": 4,
    "maja": 5, "maj": 5,
    "czerwca": 6, "czerwiec": 6,
    "lipca": 7, "lipiec": 7,
    "sierpnia": 8, "sierpień": 8,
    "września": 9, "wrzesień": 9,
    "października": 10, "październik": 10,
    "listopada": 11, "listopad": 11,
    "grudnia": 12, "grudzień": 12,
}

IGNORE_TITLES = [
    "informacja",
    "godziny pracy",
    "komunikat",
    "życzenia",
    "regulamin",
    "deklaracja dostępności"
]


class MbpKkPlScraper:
    def __init__(self):
        self.source_name = "mbpkk_pl"
        self.base_url = "https://mbpkk.pl"
        self.events_url = "https://mbpkk.pl/aktualne-wydarzenia/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _parse_polish_date(self, text: str) -> str:
        # Priorytet: szukanie frazy "Termin: DD.MM.YYYY"
        termin_match = re.search(r"Termin:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", text, re.IGNORECASE)
        if termin_match:
            d, m, y = termin_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # Standardowy format DD.MM.YYYY
        d_match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
        if d_match:
            d, m, y = d_match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # Słowny format DD [miesiąc] YYYY
        month_pattern = "|".join(POLISH_MONTH_MAP.keys())
        word_match = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})\b", text, re.IGNORECASE)
        if word_match:
            d, m_name, y = word_match.groups()
            m = POLISH_MONTH_MAP[m_name.lower()]
            return f"{y}-{m:02d}-{int(d):02d}"

        return ""

    def _parse_event_time(self, text: str) -> str:
        # Celujemy precyzyjnie w zapis po słowie godzina/godz. (np. "godz. 16:00", "godz 17.00")
        time_match = re.search(r"godz(?:ina|\.)?\s*([01]?[0-9]|2[0-3])[:.]([0-5][0-9])", text, re.IGNORECASE)
        if time_match:
            h, m = time_match.groups()
            return f"{int(h):02d}:{m}"
        return "Według harmonogramu"

    def fetch_events(self) -> list[dict]:
        events = []
        try:
            resp = requests.get(self.events_url, headers=self.headers, timeout=12)
            if resp.status_code != 200:
                return events

            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Wyszukiwanie kontenerów z wpisami
            cards = soup.select("article, .post, .elementor-post, .event-item")
            if not cards:
                cards = soup.select(".content-area div.col-md-4, .site-main > div")

            for card in cards:
                # Usunięcie metadanych redakcyjnych (autor, data publikacji wpisu)
                for meta in card.select(".entry-meta, .post-meta, .author, .posted-on, time"):
                    meta.decompose()

                title_el = card.select_one("h2, h3, h4, .entry-title, .elementor-post__title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                
                # Odrzucenie zbyt krótkich nazw i wpisów technicznych
                if len(title) < 5 or any(ignored in title.lower() for ignored in IGNORE_TITLES):
                    continue

                card_text = card.get_text(" ", strip=True)
                date_str = self._parse_polish_date(card_text)

                if not date_str:
                    continue

                time_start = self._parse_event_time(card_text)

                link_el = card.select_one("a[href]")
                url = urljoin(self.base_url, link_el["href"]) if link_el else self.events_url

                img_el = card.select_one("img[src]")
                image_url = ""
                if img_el:
                    src = img_el.get("src", "")
                    if not src.startswith("data:"):
                        image_url = urljoin(self.base_url, src)

                desc_el = card.select_one("p, .entry-summary, .elementor-post__excerpt")
                raw_desc = desc_el.get_text(" ", strip=True) if desc_el else card_text
                
                # Czyszczenie opisu z pozostałości znaczników czasowych i autorów
                clean_desc = re.sub(r"^[A-ZŁŚŻŹ][a-ząćęłńóśźż]+\s+[A-ZŁŚŻŹ][a-ząćęłńóśźż]+\s+\d{4}-\d{2}-\d{2}T[^\s]+", "", raw_desc)
                clean_desc = clean_desc.replace("Czytaj więcej", "").strip(" |–- \n\t")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time_start": time_start,
                    "venue": "Miejska Biblioteka Publiczna w Kędzierzynie-Koźlu",
                    "address": "Rynek 3, Kędzierzyn-Koźle",
                    "price_range": "Wstęp wolny",
                    "description": clean_desc,
                    "image_url": image_url,
                    "url": url,
                    "source": self.source_name,
                    "organizer": "Miejska Biblioteka Publiczna"
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania: {e}")

        return events


if __name__ == "__main__":
    scraper = MbpKkPlScraper()
    results = scraper.fetch_events()
    print(f"\nZnaleziono poprawnych wydarzeń: {len(results)}\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))