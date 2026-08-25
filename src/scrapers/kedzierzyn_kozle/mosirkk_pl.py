import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

class MosirKkPlScraper:
    def __init__(self):
        self.source_name = "mosirkk_pl"
        self.base_url = "https://www.mosirkk.pl"
        # Aktualności i wydarzenia MOSiR lądują bezpośrednio na stronie głównej
        self.events_url = "https://www.mosirkk.pl"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_events(self) -> list[dict]:
        events = []
        try:
            resp = requests.get(self.events_url, headers=self.headers, timeout=12)
            if resp.status_code != 200:
                return events

            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 1. Zawężenie skanowania do głównego kontenera (omijanie bocznych paneli i menu)
            main_content = (
                soup.find("main") or 
                soup.find(id="sp-component") or 
                soup.find(id="content") or 
                soup.find(class_="blog") or 
                soup
            )
            
            # Szukamy kafelków (wpisów)
            cards = main_content.select(".item, article, .blog-item, .news-item")
            if not cards:
                cards = main_content.select(".content .row > div")

            for card in cards:
                title_el = card.select_one("h2, h3, h4, .page-header, .title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                
                # Bezpiecznik: twarde odrzucenie znanych statycznych przycisków
                if len(title) < 5 or title.lower() in ["mistrzostwa miasta", "pozostałe imprezy", "kalendarz imprez sportowych mosir", "wakacje na sportowo 2026"]:
                    continue

                # 2. Bezwzględne poszukiwanie daty. Jeśli brak daty -> to przycisk, ignorujemy.
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
                        # Brak daty w treści wyklucza kafelek z bycia wydarzeniem
                        continue

                time_match = re.search(r"\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b", card_text)
                time_start = time_match.group(0) if time_match else "Według harmonogramu"

                link_el = card.select_one("a[href]")
                url = urljoin(self.base_url, link_el["href"]) if link_el else self.base_url

                img_el = card.select_one("img[src]")
                image_url = ""
                if img_el:
                    src = img_el.get("src", "")
                    if not src.startswith("data:"):
                        image_url = urljoin(self.base_url, src)

                desc_el = card.select_one("p, .introtext, .desc")
                desc = desc_el.get_text(" ", strip=True) if desc_el else card_text[:300]
                
                # Oczyszczanie opisu ze znalezisk typu data przyklejona do "więcej..."
                desc = re.sub(r"^\d{1,2}\.\d{1,2}\.\d{4}", "", desc).replace("więcej...", "").strip()

                events.append({
                    "title": title,
                    "date": date_str,
                    "time_start": time_start,
                    "venue": "Obiekty MOSiR Kędzierzyn-Koźle",
                    "address": "al. Jana Pawła II 29, Kędzierzyn-Koźle",
                    "price_range": "Sprawdź cennik",
                    "description": desc,
                    "image_url": image_url,
                    "url": url,
                    "source": self.source_name
                })

        except Exception as e:
            print(f"[{self.source_name}] Błąd parsowania: {e}")

        return events