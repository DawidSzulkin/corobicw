import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.infrastructure.scrapers.base import BaseScraper

POLISH_MONTHS = {
    "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
    "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
    "września": "09", "października": "10", "listopada": "11", "grudnia": "12"
}

RE_DATE = re.compile(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", re.IGNORECASE)
RE_TIME = re.compile(r"\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b")
RE_PRICE = re.compile(r"(?:Bilety\s*:?\s*)?(\d{2,3}(?:\s*;\s*\d{2,3})*\s*zł)", re.IGNORECASE)


class NcppOpolePlScraper(BaseScraper):
    def __init__(self):
        super().__init__(source_name="ncpp_opole_pl", base_url="https://ncpp.opole.pl")
        self.city_tag = "opole"
        self.city_name = "Opole"
        self.events_url = "https://ncpp.opole.pl/menu/kup-bilet.html"

    def _parse_date(self, text: str) -> str:
        clean_text = text.replace('\xa0', ' ')
        match = RE_DATE.search(clean_text)
        if match:
            day, month_name, year = match.groups()
            month = POLISH_MONTHS.get(month_name.lower(), "")
            if month:
                return f"{year}-{int(month):02d}-{int(day):02d}"
        return ""

    def _parse_time(self, text: str) -> str:
        clean_text = text.replace('\xa0', ' ')
        match = RE_TIME.search(clean_text)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
        return "19:00"

    def _extract_image(self, soup: BeautifulSoup, page_html: str) -> str:
        # 1. Szukanie ścieżek do plakatów w katalogu /foto/koncerty/ lub /foto/wydarzenia/
        raw_matches = re.findall(r'["\'](/?[^"\']*foto/(?:koncerty|wydarzenia|repertuar)/[^"\']+\.(?:jpg|jpeg|png|webp))["\']', page_html, re.IGNORECASE)
        for m in raw_matches:
            clean_rel = m.lstrip('/')
            return f"https://ncpp.opole.pl/{clean_rel}"

        # 2. Szukanie w tagach img z pominięciem ikon i logo
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
            if not src or "lazy" in src.lower():
                continue
            src_lower = src.lower()
            if any(k in src_lower for k in ["logo", "icon", "bip", "wcag", "bilet_", "partner"]):
                continue
            if any(ext in src_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                clean_rel = src.lstrip('/')
                return f"https://ncpp.opole.pl/{clean_rel}"

        return ""

    def _extract_title(self, soup: BeautifulSoup, fallback_url: str) -> str:
        for h in soup.find_all(["h1", "h2"]):
            txt = h.get_text(" ", strip=True)
            if txt and len(txt) > 2 and "partnerzy" not in txt.lower():
                return re.sub(r"\s+", " ", txt).strip()
        slug = fallback_url.split("/")[-1].split(".html")[0].rsplit("_", 1)[0]
        return slug.replace("-", " ").title()

    def _scrape_detail_page(self, event_url: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.session.get(event_url, timeout=(3.05, 8.0))
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.content, "html.parser")
            title = self._extract_title(soup, event_url)
            if not title:
                return None

            main_el = soup.select_one(".content, #content, .text, article, main") or soup.body
            main_text = main_el.get_text("\n", strip=True) if main_el else ""

            date_iso = self._parse_date(main_text)
            if not date_iso:
                return None
            time_str = self._parse_time(main_text)

            venue = "Narodowe Centrum Polskiej Piosenki"
            for v_candidate in ["Taras Amfiteatru NCPP", "Amfiteatr NCPP", "Sala Kameralna NCPP", "Centrum Wystawienniczo-Kongresowe"]:
                if v_candidate.lower() in main_text.lower():
                    venue = v_candidate
                    break

            price_range = "Bilety płatne (NCPP)"
            lower_text = main_text.lower()
            is_free = "wstep wolny" in lower_text or "wstęp wolny" in lower_text
            
            if is_free:
                price_range = "Wstęp wolny"
            else:
                price_match = RE_PRICE.search(main_text)
                if price_match:
                    price_range = f"Bilety: {price_match.group(1)}"

            discounts = []
            if is_free:
                discounts.append({"type": "free", "label": "Wstęp wolny", "desc": "Wydarzenie plenerowe – bezpłatne dla wszystkich."})
            else:
                discounts.append({"type": "kids", "label": "Dzieci do lat 7", "desc": "Wstęp bezpłatny pod opieką rodzica (z wył. cyklu 'Dziecięce encepence')."})
                discounts.append({"type": "accessibility", "label": "Osoby na wózkach", "desc": "Dedykowana platforma w Amfiteatrze. Bilet dla opiekuna: kasa@ncpp.opole.pl."})
                discounts.append({"type": "commercial", "label": "Impreza komercyjna", "desc": "Brak zniżek studenckich/senioralnych – ceny jednolite na sektory."})

            ticket_url = event_url
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if "bilety.ncpp.opole.pl" in href:
                    ticket_url = href
                    break

            raw_img = self._extract_image(soup, resp.text)
            thumb_path = self.save_thumbnail(raw_img, title, prefix="ncpp_opole") if raw_img else ""

            paragraphs = []
            for p in main_el.find_all(["p", "div"]):
                p_txt = p.get_text(" ", strip=True)
                if len(p_txt) > 40 and not any(k in p_txt.lower() for k in ["partnerzy ncpp", "deklaracja dostępności", "bilety:", "kup bilet"]):
                    if p_txt not in paragraphs:
                        paragraphs.append(p_txt)
            description = "\n\n".join(paragraphs[:4]) if paragraphs else f"{title} w {venue}. Czas: {date_iso} {time_str}."

            return {
                "title": title,
                "date_start": date_iso,
                "date_end": date_iso,
                "time_start": time_str,
                "venue": venue,
                "address": f"{venue}, Opole",
                "price_range": price_range,
                "discounts": discounts,
                "description": description,
                "image_url": thumb_path or raw_img,
                "source_url": ticket_url,
                "organizer": "Narodowe Centrum Polskiej Piosenki",
                "source": self.source_name,
                "category": "Koncert",
                "city_tag": self.city_tag
            }
        except Exception:
            return None

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        try:
            resp = self.session.get(self.events_url, timeout=(3.05, 8.0))
            if resp.status_code != 200:
                return events

            soup = BeautifulSoup(resp.content, "html.parser")
            seen_urls = set()
            urls_to_scrape = []

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if re.search(r"kup-bilet/[^/]+_\d+\.html", href):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        urls_to_scrape.append(full_url)

            print(f"[{self.source_name}] Pobieranie szczegółów i plakatów dla {len(urls_to_scrape)} wydarzeń...")
            for url in urls_to_scrape:
                ev = self._scrape_detail_page(url)
                if ev:
                    events.append(ev)

        except Exception as e:
            print(f"[{self.source_name}] Błąd: {e}")

        print(f"[{self.source_name}] Zakończono. Sparsowano: {len(events)} wydarzeń NCPP.")
        return events