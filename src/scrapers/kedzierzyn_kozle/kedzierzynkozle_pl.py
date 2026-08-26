from datetime import datetime
import os
import re
import sys
import time
from typing import Any, Dict, List, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import urllib3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class KedzierzynKozlePlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="kedzierzynkozle_pl",
            base_url="https://kedzierzynkozle.pl"
        )
        self.seen_urls: Set[str] = set()

    def _get_soup(self, url: str) -> BeautifulSoup:
        resp = self.session.get(url, timeout=(3.0, 10.0), verify=False)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _clean_title(self, raw_title: str) -> str:
        cleaned = re.sub(
            r"^(czytaj więcej o wydarzeniu|czytaj więcej o|go to events list from day:?)\s*",
            "",
            raw_title,
            flags=re.IGNORECASE
        )
        return cleaned.strip()

    def _fetch_details(self, event_url: str, title: str) -> Dict[str, Any]:
        default_img = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"
        try:
            time.sleep(0.03)
            soup = self._get_soup(event_url)

            article = (
                soup.find("article") or
                soup.find("div", class_="node-content") or
                soup.find("div", class_="field-name-body") or
                soup.find("div", id="content") or
                soup
            )

            article_text = article.get_text(separator="\n")

            time_start = "Według harmonogramu"
            time_match = re.search(r"(\b[0-2]?[0-9]:[0-5][0-9]\b)", article_text)
            if time_match:
                time_start = time_match.group(1)

            venue = "Kędzierzyn-Koźle"
            drupal_venue = article.select_one(".field-name-field-miejsce-wydarzenia .field-item, .field-name-field-miejsce .field-item")
            if drupal_venue:
                candidate = drupal_venue.get_text(strip=True)
                if candidate and len(candidate) < 120:
                    venue = candidate
            else:
                for tag in article.find_all(["p", "span", "div"]):
                    if "Miejsce wydarzenia:" in tag.text and not tag.find_all(["div", "article", "section"]):
                        candidate = tag.get_text().replace("Miejsce wydarzenia:", "").strip()
                        if candidate and len(candidate) < 120 and not any(bad in candidate for bad in ["POGODA", "czcionki", "BIP", "Polski"]):
                            venue = candidate
                            break

            raw_image = ""
            for img in article.select("img"):
                src = img.get("src", "")
                if not src:
                    continue
                src_lower = src.lower()
                if any(ignored in src_lower for ignored in ["logo", "bip", "unia", "herb", "koziolk", "budzet", "icon"]):
                    continue
                raw_image = urljoin(self.base_url, src)
                break

            thumb_path = self.save_thumbnail(raw_image, title, prefix="kedzierzynkozle") if raw_image else ""

            paragraphs = article.find_all("p")
            valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
            description = "\n\n".join(valid_paragraphs) if valid_paragraphs else f"Wydarzenie w Kędzierzynie-Koźlu: {title}."

            return {
                "description": description,
                "image_url": thumb_path or raw_image or default_img,
                "time_start": time_start,
                "price_range": "Wstęp wolny / Sprawdź bilety",
                "venue": venue,
                "address": f"{venue}, Kędzierzyn-Koźle" if "Kędzierzyn" not in venue else venue
            }
        except Exception as e:
            print(f"    [Błąd pobierania {event_url}]: {e}")
            return {
                "description": f"Wydarzenie: {title}.",
                "image_url": default_img,
                "time_start": "Według harmonogramu",
                "price_range": "Sprawdź bilety",
                "venue": "Kędzierzyn-Koźle",
                "address": "Kędzierzyn-Koźle"
            }

    def scrape_month(self, year: int, month: int, today_iso: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/pl/calendar-node-field-date/month/{year}-{month:02d}"
        print(f"\n[{self.source_name}] Skanowanie widoku kalendarza: {year}-{month:02d}")

        try:
            soup = self._get_soup(url)
        except Exception as e:
            print(f"[{self.source_name}] Błąd pobierania kalendarza: {e}")
            return []

        pending_events = []
        cells = soup.select(".view-calendar td, .calendar-calendar td")

        for cell in cells:
            current_date = None
            day_link = cell.select_one("a[href*='/calendar-node-field-date/day/']")
            if day_link and day_link.get("href"):
                date_match = re.search(r"\d{4}-\d{2}-\d{2}", day_link["href"])
                if date_match:
                    current_date = date_match.group(0)

            if not current_date or current_date < today_iso:
                continue

            for link in cell.select("a[href*='/pl/wydarzenie/']"):
                href = link.get("href")
                if not href:
                    continue

                full_url = urljoin(self.base_url, href)
                if full_url in self.seen_urls:
                    continue
                self.seen_urls.add(full_url)

                title = self._clean_title(link.get_text(strip=True))
                if title:
                    pending_events.append({
                        "title": title,
                        "date_start": current_date,
                        "source_url": full_url
                    })

        print(f"[{self.source_name}] Wykryto {len(pending_events)} nadchodzących wydarzeń (>= {today_iso}).")

        new_events = []
        for item in pending_events:
            details = self._fetch_details(item["source_url"], item["title"])

            new_events.append({
                "title": item["title"],
                "date_start": item["date_start"],
                "date_end": item["date_start"],
                "time_start": details["time_start"],
                "venue": details["venue"],
                "address": details["address"],
                "price_range": details["price_range"],
                "description": details["description"],
                "image_url": details["image_url"],
                "source_url": item["source_url"],
                "source": self.source_name,
                "organizer": "Urząd Miasta Kędzierzyn-Koźle"
            })

        return new_events

    def fetch_events(self) -> List[Dict[str, Any]]:
        self.seen_urls.clear()
        today_iso = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now()
        all_events = []

        for offset in range(3):
            target_month = (now.month - 1 + offset) % 12 + 1
            target_year = now.year + ((now.month - 1 + offset) // 12)
            all_events.extend(self.scrape_month(target_year, target_month, today_iso))

        return all_events
