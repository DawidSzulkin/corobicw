from datetime import datetime
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests
import urllib3

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MosirKkPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="mosirkk_pl",
            base_url="https://www.mosirkk.pl"
        )
        self.events_url = "https://www.mosirkk.pl"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        default_img = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"

        try:
            print(f"\n[{self.source_name}] Skanowanie wydarzeń MOSiR Kędzierzyn-Koźle...")
            resp = self.session.get(self.events_url, timeout=12, verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP {resp.status_code}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")

            main_content = (
                soup.find("main") or
                soup.find(id="sp-component") or
                soup.find(id="content") or
                soup.find(class_="blog") or
                soup
            )

            cards = main_content.select(".item, article, .blog-item, .news-item")
            if not cards:
                cards = main_content.select(".content .row > div")

            for card in cards:
                title_el = card.select_one("h2, h3, h4, .page-header, .title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                if len(title) < 5 or title.lower() in [
                    "mistrzostwa miasta", "pozostałe imprezy",
                    "kalendarz imprez sportowych mosir", "wakacje na sportowo 2026"
                ]:
                    continue

                card_text = card.get_text(" ", strip=True)
                d_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", card_text)

                if d_match:
                    day, month, year = d_match.groups()
                    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                else:
                    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", card_text)
                    if iso_match:
                        date_str = iso_match.group(0)
                    else:
                        continue

                # Twarde odcięcie przeszłych wydarzeń
                if date_str < today_iso:
                    continue

                time_match = re.search(r"\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b", card_text)
                time_start = time_match.group(0) if time_match else "Według harmonogramu"

                link_el = card.select_one("a[href]")
                url = urljoin(self.base_url, link_el["href"]) if link_el else self.base_url

                img_el = card.select_one("img[src]")
                image_url = default_img
                if img_el:
                    src = img_el.get("src", "")
                    if src and not src.startswith("data:"):
                        image_url = urljoin(self.base_url, src)

                desc_el = card.select_one("p, .introtext, .desc")
                desc = desc_el.get_text(" ", strip=True) if desc_el else card_text[:300]
                desc = re.sub(r"^\d{1,2}\.\d{1,2}\.\d{4}", "", desc).replace("więcej...", "").strip()

                print(f"  [MOSiR] {date_str} | {time_start} | {title[:35]}...")

                events.append({
                    "title": title,
                    "date_start": date_str,
                    "time_start": time_start,
                    "venue": "Obiekty MOSiR Kędzierzyn-Koźle",
                    "address": "al. Jana Pawła II 29, Kędzierzyn-Koźle",
                    "price_range": "Sprawdź cennik / Wstęp wolny",
                    "description": desc,
                    "image_url": image_url,
                    "source_url": url,
                    "source": self.source_name
                })

            print(f"[{self.source_name}] Pomyślnie pobrano {len(events)} pozycji.")

        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania: {e}")

        return events