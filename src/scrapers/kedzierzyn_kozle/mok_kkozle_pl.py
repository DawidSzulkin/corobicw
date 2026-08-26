from datetime import datetime
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests
import urllib3

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MokKkozlePlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="mok_kkozle_pl",
            base_url="https://www.mok.kedzierzyn-kozle.com.pl"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.mok.kedzierzyn-kozle.com.pl/wydarzenia"
        })
        self.seen_urls: Set[str] = set()

        self.junk_keywords = [
            "poszukiwany", "poszukujemy", "rekrutacja", "sanepid", "informacja",
            "stuknęło", "jubileusz", "wspomnienia", "zapisy", "sekcje", "e-skarbonka", "mapa strony"
        ]

        self.months_map = {
            "stycz": 1, "lut": 2, "mar": 3, "kwie": 4, "maj": 5, "czerw": 6,
            "lip": 7, "sierp": 8, "wrzes": 9, "wrześ": 9, "paźdz": 10, "pazdz": 10,
            "listop": 11, "grud": 12
        }

    def _get_soup(self, url: str) -> BeautifulSoup:
        resp = self.session.get(url, timeout=12, verify=False)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _extract_event_date(self, text: str) -> Optional[str]:
        current_year = datetime.now().year

        # 1. Format DD.MM.YYYY
        match_full = re.search(r"\b([0-3]?[0-9])\.([0-1]?[0-9])\.(20\d{2})\b", text)
        if match_full:
            d, m, y = match_full.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # 2. Słowny format polski (np. "29 sierpnia 2026" lub "15 września")
        match_named = re.search(r"\b([0-3]?[0-9])\s+([a-ząćęłńóśźż]+)(?:\s+(20\d{2}))?\b", text, re.IGNORECASE)
        if match_named:
            day = int(match_named.group(1))
            month_str = match_named.group(2).lower()
            year = int(match_named.group(3)) if match_named.group(3) else current_year

            for prefix, month_num in self.months_map.items():
                if month_str.startswith(prefix):
                    return f"{year}-{month_num:02d}-{day:02d}"

        # 3. Format "w dniu DD.MM" lub "termin: DD.MM" (uzupełniamy bieżącym rokiem)
        match_short = re.search(r"(?:dnia|dzień|termin|w dniu|odbędzie się)\s*([0-3]?[0-9])\.([0-1]?[0-9])", text, re.IGNORECASE)
        if match_short:
            d, m = match_short.groups()
            return f"{current_year}-{int(m):02d}-{int(d):02d}"

        return None

    def _fetch_details(self, event_url: str, fallback_img: str) -> Optional[Dict[str, Any]]:
        try:
            time.sleep(0.05)
            soup = self._get_soup(event_url)

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
                generic_time = re.search(r"(\b[0-2]?[0-9]:[0-5][0-9]\b)", container_text)
                if generic_time:
                    time_start = generic_time.group(1)

            paragraphs = container.find_all("p")
            valid_p = [self._clean_text(p.get_text()) for p in paragraphs if len(p.get_text().strip()) > 20]
            description = "\n\n".join(valid_p) if valid_p else self._clean_text(container_text)

            image_url = fallback_img
            for img in container.select("img"):
                src = img.get("src", "")
                if not src:
                    continue
                src_lower = src.lower()
                if any(bad in src_lower for bad in ["logo", "bip", "icon", "arrow", "social", "cookie", "banner"]):
                    continue
                image_url = urljoin(self.base_url, src)
                break

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
            elif "twierdz" in lower_text or "skarbowa" in lower_text:
                venue = "Kino Twierdza (ul. Skarbowa 10)"
            elif "koźle" in lower_text:
                venue = "DK Koźle (ul. Skarbowa 10)"

            return {
                "date_start": real_date,
                "description": description,
                "image_url": image_url,
                "time_start": time_start,
                "price_range": price_range,
                "venue": venue,
                "address": venue
            }
        except Exception as e:
            print(f"    [Błąd pobierania detali MOK]: {e}")
            return None

    def fetch_events(self) -> List[Dict[str, Any]]:
        self.seen_urls.clear()
        pending_items = []
        today_iso = datetime.now().strftime("%Y-%m-%d")

        print(f"\n[{self.source_name}] Skanowanie aktualnego repertuaru MOK...")

        for page in range(1, 5):
            api_url = f"{self.base_url}/index.php?option=com_minitekwall&task=masonry.getContent&widget_id=1&page={page}"
            try:
                resp = self.session.get(api_url, timeout=10, verify=False)
                if resp.status_code != 200 or not resp.text.strip():
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select(".mnwall-item")
                if not items:
                    break

                for item in items:
                    data_id = item.get("data-id")
                    title = item.get("data-title")

                    if not data_id or not title:
                        continue

                    title_clean = self._clean_text(title).title()

                    if any(junk in title.lower() for junk in self.junk_keywords):
                        continue

                    full_url = f"{self.base_url}/index.php?option=com_content&view=article&id={data_id}"
                    if full_url in self.seen_urls:
                        continue
                    self.seen_urls.add(full_url)

                    thumb_img = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"
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
            details = self._fetch_details(item["source_url"], fallback_img=item["thumb_img"])
            if not details:
                continue

            # Odrzucenie wydarzeń przeszłych
            if details["date_start"] < today_iso:
                continue

            print(f"  [MOK] {details['date_start']} | {details['time_start']} | {details['price_range']} | {item['title'][:35]}...")

            valid_events.append({
                "title": item["title"],
                "date_start": details["date_start"],
                "source_url": item["source_url"],
                "time_start": details["time_start"],
                "description": details["description"],
                "image_url": details["image_url"],
                "venue": details["venue"],
                "address": details["address"],
                "price_range": details["price_range"],
                "source": self.source_name
            })

        print(f"[{self.source_name}] Zwrócono {len(valid_events)} aktywnych wydarzeń.")
        return valid_events