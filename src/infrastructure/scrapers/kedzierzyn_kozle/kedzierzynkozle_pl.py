import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Set

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.infrastructure.scrapers.base import BaseScraper

MONTHS_PL = {
    'styczeń': '01', 'stycznia': '01',
    'luty': '02', 'lutego': '02',
    'marzec': '03', 'marca': '03',
    'kwiecień': '04', 'kwietnia': '04',
    'maj': '05', 'maja': '05',
    'czerwiec': '06', 'czerwca': '06',
    'lipiec': '07', 'lipca': '07',
    'sierpień': '08', 'sierpnia': '08',
    'wrzesień': '09', 'września': '09',
    'październik': '10', 'października': '10',
    'listopad': '11', 'listopada': '11',
    'grudzień': '12', 'grudnia': '12'
}

class KedzierzynKozlePlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(
            source_name="kedzierzynkozle_pl",
            base_url="https://kedzierzynkozle.pl"
        )
        self.seen_urls: Set[str] = set()

    def _parse_date_str(self, text: str) -> str | None:
        if not text:
            return None
        m = re.search(r'(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})', text.strip(), re.IGNORECASE)
        if m:
            day, month_name, year = m.groups()
            month_num = MONTHS_PL.get(month_name.lower())
            if month_num:
                return f"{year}-{month_num}-{int(day):02d}"
        return None

    def _parse_date_block(self, date_block) -> dict:
        res = {'start_date': None, 'end_date': None, 'start_time': None, 'end_time': None, 'is_all_day': False}
        if not date_block:
            return res

        date_values = date_block.select('.date-value')
        if len(date_values) >= 1:
            d_val = date_values[0]
            start_el = d_val.select_one('.date-display-start')
            end_el = d_val.select_one('.date-display-end')
            single_el = d_val.select_one('.date-display-single')

            if start_el and end_el:
                res['start_date'] = self._parse_date_str(start_el.get_text(strip=True))
                res['end_date'] = self._parse_date_str(end_el.get_text(strip=True))
            elif single_el:
                res['start_date'] = self._parse_date_str(single_el.get_text(strip=True))
                res['end_date'] = res['start_date']

        if len(date_values) >= 2:
            t_val = date_values[1]
            t_text = t_val.get_text(separator=' ', strip=True).lower()
            if 'całodzienne' in t_text:
                res['is_all_day'] = True
            else:
                times = re.findall(r'\b(\d{1,2}:\d{2})\b', t_text)
                if len(times) == 1:
                    res['start_time'] = times[0]
                elif len(times) >= 2:
                    res['start_time'] = times[0]
                    res['end_time'] = times[1]

        return res

    def _fetch_description(self, relative_url: str) -> str:
        """Pobiera wyłącznie pełny opis z podstrony (miniatura i adres są z listy)."""
        try:
            soup = self.get_soup(relative_url)
            article = soup.select_one(".field-name-body, .node-content, #content")
            if article:
                paragraphs = article.find_all("p")
                valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
                if valid_paragraphs:
                    return " ".join(valid_paragraphs)
                return article.get_text(separator=" ", strip=True)[:600]
        except Exception as e:
            print(f"[{self.source_name}] Błąd pobierania opisu {relative_url}: {e}")
        return ""

    def scrape_month(self, year: int, month: int, today_iso: str) -> List[Dict[str, Any]]:
        url = f"/pl/calendar-node-field-date/month/{year}-{month:02d}"
        print(f"[{self.source_name}] Skanowanie kalendarza: {year}-{month:02d}")

        try:
            soup = self.get_soup(url)
        except Exception as e:
            print(f"[{self.source_name}] Błąd pobierania kalendarza: {e}")
            return []

        new_events = []
        rows = soup.select('.view-Wydarzenia .views-row')

        for row in rows:
            title_el = row.select_one('.views-field-title .field-content')
            link_el = row.select_one('.view-read-more a')

            if not title_el or not link_el:
                continue

            relative_url = link_el.get('href', '')
            full_url = f"{self.base_url}{relative_url}" if relative_url.startswith('/') else f"{self.base_url}/{relative_url}"
            
            if full_url in self.seen_urls:
                continue

            date_block = row.select_one('.data-wydarzenia')
            date_meta = self._parse_date_block(date_block)
            
            check_date = date_meta['end_date'] or date_meta['start_date']
            if not check_date or check_date < today_iso:
                continue
                
            self.seen_urls.add(full_url)
            title = title_el.get_text(strip=True)

            location_el = row.select_one('.views-field-field-miejsce-wydarzenia .field-content')
            venue = location_el.get_text(strip=True) if location_el else "Kędzierzyn-Koźle"

            img_el = row.select_one('.views-field-field-obrazek img')
            raw_image = img_el.get('src') if img_el else ""
            thumb_path = self.save_thumbnail(raw_image, title, prefix="kk") if raw_image else ""

            description = self._fetch_description(relative_url)
            if not description:
                description = f"Wydarzenie w Kędzierzynie-Koźlu: {title}."

            new_events.append({
                "title": title,
                "date_start": date_meta['start_date'],
                "date_end": date_meta['end_date'],
                "time_start": date_meta['start_time'] or "Według harmonogramu",
                "venue": venue,
                "address": f"{venue}, Kędzierzyn-Koźle" if "Kędzierzyn" not in venue else venue,
                "price_range": "Wstęp wolny / Sprawdź bilety",
                "description": description,
                "image_url": thumb_path or raw_image or "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80",
                "source_url": full_url,
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
            events = self.scrape_month(target_year, target_month, today_iso)
            all_events.extend(events)

        print(f"[{self.source_name}] Łącznie pobrano {len(all_events)} unikalnych wydarzeń.")
        return all_events
