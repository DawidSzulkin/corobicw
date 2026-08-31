import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper

MONTHS_PL = {
    'stycznia': 1, 'styczeń': 1, 'sty': 1,
    'lutego': 2, 'luty': 2, 'lut': 2,
    'marca': 3, 'marzec': 3, 'mar': 3,
    'kwietnia': 4, 'kwiecień': 4, 'kwi': 4,
    'maja': 5, 'maj': 5,
    'czerwca': 6, 'czerwiec': 6, 'cze': 6,
    'lipca': 7, 'lipiec': 7, 'lip': 7,
    'sierpnia': 8, 'sierpień': 8, 'sie': 8,
    'września': 9, 'wrzesień': 9, 'wrz': 9,
    'października': 10, 'październik': 10, 'paź': 10, 'paz': 10,
    'listopada': 11, 'listopad': 11, 'lis': 11,
    'grudnia': 12, 'grudzień': 12, 'gru': 12
}

JUNK_KEYWORDS = [
    "poszukiwany", "poszukujemy", "rekrutacja", "sanepid", "informacja",
    "stuknęło", "jubileusz", "wspomnienia", "zapisy", "sekcje", "e-skarbonka", "mapa strony"
]

class MokKkozlePlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="mok_kkozle_pl",
            base_url="https://www.mok.kedzierzyn-kozle.com.pl"
        )
        self.session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.mok.kedzierzyn-kozle.com.pl/wydarzenia"
        })
        self.seen_urls: Set[str] = set()

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _extract_event_date(self, text: str) -> Optional[str]:
        now = datetime.now()

        # 1. Format DD.MM.YYYY
        match_full = re.search(r"\b([0-3]?[0-9])\.([0-1]?[0-9])\.(20\d{2})\b", text)
        if match_full:
            d, m, y = match_full.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # 2. Słowny format polski: DD [Miesiąc] (YYYY)
        match_named = re.search(r"\b([0-3]?[0-9])\s+([a-ząćęłńóśźż]+)(?:\s+(20\d{2}))?\b", text, re.IGNORECASE)
        if match_named:
            day = int(match_named.group(1))
            month_str = match_named.group(2).lower()
            month_num = None

            for name, idx in MONTHS_PL.items():
                if month_str.startswith(name) or name.startswith(month_str):
                    month_num = idx
                    break

            if month_num:
                if match_named.group(3):
                    year = int(match_named.group(3))
                else:
                    # Anty-zombie: nie dodajemy roku w przód, chyba że jesteśmy na przełomie roku
                    if month_num >= now.month:
                        year = now.year
                    elif now.month >= 11 and month_num <= 2:
                        year = now.year + 1
                    else:
                        year = now.year
                return f"{year}-{month_num:02d}-{day:02d}"

        # 3. Format "dnia DD.MM" lub "termin: DD.MM"
        match_short = re.search(r"(?:dnia|dzień|termin|w dniu|odbędzie się)\s*([0-3]?[0-9])\.([0-1]?[0-9])", text, re.IGNORECASE)
        if match_short:
            d, m = match_short.groups()
            m_val = int(m)
            if 1 <= m_val <= 12 and 1 <= int(d) <= 31:
                if m_val >= now.month:
                    year = now.year
                elif now.month >= 11 and m_val <= 2:
                    year = now.year + 1
                else:
                    year = now.year
                return f"{year}-{m_val:02d}-{int(d):02d}"

        return None

    def _fetch_details(self, event_url: str, title: str, fallback_img: str) -> Optional[Dict[str, Any]]:
        default_img = "/assets/placeholder.svg"
        try:
            soup = self.get_soup(event_url)

            for unwanted in soup.select("header, footer, nav, script, style, .sidebar, #sidebar, .moduletable, .nav"):
                unwanted.decompose()

            container = soup.select_one(".item-page, article, main, #content") or soup
            container_text = container.get_text(separator="\n")

            real_date = self._extract_event_date(container_text)
            if not real_date:
                return None

            time_start = "Według harmonogramu"
            time_match = re.search(r"(?:godz\.?|godzinie)\s*([0-2]?[0-9][:.][0-5][0-9])", container_text, re.IGNORECASE)
            if time_match:
                time_start = time_match.group(1).replace(".", ":")
            else:
                generic_time = re.search(r"\b([0-2]?[0-9]:[0-5][0-9])\b", container_text)
                if generic_time:
                    time_start = generic_time.group(1)

            paragraphs = container.find_all("p")
            valid_p = [self._clean_text(p.get_text()) for p in paragraphs if len(p.get_text().strip()) > 20]
            description = "\n\n".join(valid_p) if valid_p else self._clean_text(container_text)[:600]

            raw_image = fallback_img
            for img in container.select("img"):
                src = img.get("src", "")
                if not src:
                    continue
                src_lower = src.lower()
                if any(bad in src_lower for bad in ["logo", "bip", "icon", "arrow", "social", "cookie", "banner"]):
                    continue
                raw_image = urljoin(self.base_url, src)
                break

            thumb_path = self.save_thumbnail(raw_image, title, prefix="mok_kk") if (raw_image and "unsplash" not in raw_image) else ""

            price_range = "Sprawdź bilety / Wstęp wolny"
            price_match = re.search(r"(?:koszt|cena|bilet[yw]?|wstęp)[\s\w]*?[-:]\s*(\d+[\s,-]*zł|wstęp wolny|bezpłatn\w+)", container_text, re.IGNORECASE)
            if price_match:
                price_range = price_match.group(1).strip()
            elif "wstęp wolny" in container_text.lower() or "bezpłatn" in container_text.lower():
                price_range = "Wstęp wolny"

            venue = "MOK Kędzierzyn-Koźle"
            lower_text = container_text.lower()
            if "park w sławięcicach" in lower_text or "sławięcic" in lower_text:
                venue = "Park w Sławięcicach"
            elif "chemik" in lower_text or "jana pawła" in lower_text:
                venue = "DK Chemik (al. Jana Pawła II 27)"
            elif "twierdz" in lower_text or "skarbowa" in lower_text or "koźle" in lower_text:
                venue = "DK Koźle / Kino Twierdza (ul. Skarbowa 10)"
            elif "lech" in lower_text or "wyzwolenia" in lower_text:
                venue = "DK Lech (ul. Wyzwolenia 7)"

            return {
                "date_start": real_date,
                "description": description,
                "image_url": thumb_path or raw_image or default_img,
                "time_start": time_start,
                "price_range": price_range,
                "venue": venue,
                "address": venue
            }
        except Exception as e:
            print(f"    [Błąd pobierania detali MOK {event_url}]: {e}")
            return None

    def fetch_events(self) -> List[Dict[str, Any]]:
        self.seen_urls.clear()
        pending_items = []
        today_iso = datetime.now().strftime("%Y-%m-%d")

        print(f"[{self.source_name}] Skanowanie repertuaru MOK Kędzierzyn-Koźle...")

        for page in range(1, 5):
            api_url = f"/index.php?option=com_minitekwall&task=masonry.getContent&widget_id=1&page={page}"
            try:
                soup = self.get_soup(api_url)
                items = soup.select(".mnwall-item")
                if not items:
                    break

                for item in items:
                    data_id = item.get("data-id")
                    title = item.get("data-title")

                    if not data_id or not title:
                        continue

                    title_clean = self._clean_text(title)

                    if any(junk in title.lower() for junk in JUNK_KEYWORDS):
                        continue

                    full_url = f"{self.base_url}/index.php?option=com_content&view=article&id={data_id}"
                    if full_url in self.seen_urls:
                        continue
                    self.seen_urls.add(full_url)

                    thumb_img = "/assets/placeholder.svg"
                    photo_div = item.select_one(".mnwall-photo-link, .mnwall-item-photo")
                    if photo_div and photo_div.get("style"):
                        img_match = re.search(r"url\(['\"]?(.*?)['\"]?\)", photo_div["style"])
                        if img_match:
                            thumb_img = urljoin(self.base_url, img_match.group(1))

                    pending_items.append({
                        "title": title_clean,
                        "source_url": full_url,
                        "thumb_img": thumb_img
                    })

            except Exception as e:
                print(f"  [Błąd pobierania strony {page}]: {e}")
                break

        valid_events = []
        for item in pending_items:
            details = self._fetch_details(item["source_url"], item["title"], fallback_img=item["thumb_img"])
            if not details:
                continue

            if details["date_start"] < today_iso:
                continue

            valid_events.append({
                "title": item["title"],
                "date_start": details["date_start"],
                "date_end": details["date_start"],
                "time_start": details["time_start"],
                "venue": details["venue"],
                "address": details["address"],
                "price_range": details["price_range"],
                "description": details["description"],
                "image_url": details["image_url"],
                "source_url": item["source_url"],
                "source": self.source_name,
                "organizer": "Miejski Ośrodek Kultury w Kędzierzynie-Koźlu"
            })

        print(f"[{self.source_name}] Zwrócono {len(valid_events)} aktywnych wydarzeń.")
        return valid_events
