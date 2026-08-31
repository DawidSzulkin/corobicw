import json
import re
import urllib3
from pathlib import Path
from bs4 import BeautifulSoup
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Sprawdzenie pojedynczej podstrony z KupBilecik
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
search_url = "https://www.kupbilecik.pl/szukaj/?q=Bielsko-Bia%C5%82a"
resp = requests.get(search_url, headers=headers, verify=False, timeout=10)
soup = BeautifulSoup(resp.text, "html.parser")

first_link = soup.select_one("a[href*='/imprezy/']")
if not first_link:
    print("[!] Nie znaleziono żadnego linku na liście wyszukiwania.")
    exit(1)

event_url = "https://www.kupbilecik.pl" + first_link["href"] if first_link["href"].startswith("/") else first_link["href"]
print(f"[*] Testowanie struktury podstrony: {event_url}")

sub_resp = requests.get(event_url, headers=headers, verify=False, timeout=10)
sub_soup = BeautifulSoup(sub_resp.text, "html.parser")

# Sprawdzamy obecność Schema.org
json_ld_data = None
for s in sub_soup.find_all("script", type="application/ld+json"):
    if s.string and "Event" in s.string:
        try:
            json_ld_data = json.loads(s.string)
            break
        except Exception:
            pass

print("\n" + "="*60)
print(" DANE WYCIĄGNIĘTE Z PODSTRONY (JSON-LD / META)")
print("="*60)
if json_ld_data:
    print(f"[+] Nazwa (Schema):   {json_ld_data.get('name')}")
    print(f"[+] Data (Schema):    {json_ld_data.get('startDate')}")
    loc = json_ld_data.get('location', {})
    if isinstance(loc, dict):
        print(f"[+] Miejsce (Schema): {loc.get('name')}")
        addr = loc.get('address')
        if isinstance(addr, dict):
            print(f"[+] Adres (Schema):   {addr.get('streetAddress')}, {addr.get('addressLocality')}")
else:
    print("[-] Brak Schema JSON-LD. Sprawdzanie tagów H1 i tekstu:")
    h1 = sub_soup.select_one("h1")
    print(f"[+] H1: {h1.get_text(strip=True) if h1 else 'Brak'}")

# 2. Zapis docelowego kodu scrapera z pełną obsługą Schema + Fallback
scraper_code = """import re
import json
import urllib.parse
import urllib3
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, unquote
from bs4 import BeautifulSoup
from src.infrastructure.scrapers.base import BaseScraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class KupBilecikPlScraper(BaseScraper):
    def __init__(self, city_tag: str = "kedzierzyn_kozle", partner_id: str = ""):
        super().__init__(source_name="kupbilecik_pl", base_url="https://www.kupbilecik.pl")
        self.city_tag = city_tag.strip().lower()
        self.partner_id = partner_id

        if "kedzierzyn" in self.city_tag:
            self.search_query = "Kędzierzyn"
            self.canonical_city = "Kędzierzyn-Koźle"
            self.required_slugs = ["kędzierzyn", "kedzierzyn"]
        elif "bielsko" in self.city_tag:
            self.search_query = "Bielsko-Biała"
            self.canonical_city = "Bielsko-Biała"
            self.required_slugs = ["bielsko"]
        elif "opole" in self.city_tag:
            self.search_query = "Opole"
            self.canonical_city = "Opole"
            self.required_slugs = ["opole"]
        else:
            self.search_query = self.city_tag.replace("_", " ")
            self.canonical_city = self.city_tag.replace("_", " ").title()
            self.required_slugs = [self.city_tag.replace("_", " ")]

        self.events_url = f"{self.base_url}/szukaj/?q={quote_plus(self.search_query)}"

    def _format_url(self, raw_url: str) -> str:
        clean_url = urljoin(self.base_url, raw_url)
        if self.partner_id:
            sep = "&" if "?" in clean_url else "?"
            return f"{clean_url}{sep}pv={self.partner_id}"
        return clean_url

    def _scrape_detail_page(self, event_url: str, fallback_title: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.session.get(
                event_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=(3.05, 10),
                verify=False
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            
            title = fallback_title
            date_iso = ""
            time_str = "Według harmonogramu"
            venue = ""
            street_address = ""
            description = ""
            image_url = ""

            # 1. GŁÓWNA ŚCIEŻKA: Pobieranie z JSON-LD Schema.org
            for s in soup.find_all("script", type="application/ld+json"):
                if not s.string:
                    continue
                try:
                    data = json.loads(s.string.strip())
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type") in ["Event", "TheaterEvent", "MusicEvent", "ComedyEvent"]:
                            if item.get("name"):
                                title = item.get("name").strip()
                            if item.get("description"):
                                description = item.get("description").strip()
                            if item.get("image"):
                                img = item.get("image")
                                image_url = img if isinstance(img, str) else (img[0] if isinstance(img, list) else img.get("url", ""))
                            
                            start_date = item.get("startDate", "")
                            if "T" in start_date:
                                date_iso, raw_time = start_date.split("T")[:2]
                                time_str = raw_time[:5]
                            elif start_date:
                                date_iso = start_date[:10]

                            loc = item.get("location")
                            if isinstance(loc, dict):
                                venue = loc.get("name", "").strip()
                                addr = loc.get("address")
                                if isinstance(addr, dict):
                                    street_address = addr.get("streetAddress", "").strip()
                                elif isinstance(addr, str):
                                    street_address = addr.strip()
                            break
                except Exception:
                    pass

            # 2. FALLBACK HTML (jeśli brak JSON-LD)
            if not date_iso:
                h1_el = soup.select_one("h1")
                if h1_el:
                    title = h1_el.get_text(strip=True)
                
                body_text = soup.get_text(" ", strip=True)
                d_match = re.search(r"\\b(\\d{4}-\\d{2}-\\d{2})\\b", body_text)
                if d_match:
                    date_iso = d_match.group(1)
                
                t_match = re.search(r"\\b([01]?[0-9]|2[0-3]):([0-5][0-9])\\b", body_text)
                if t_match:
                    time_str = f"{int(t_match.group(1)):02d}:{t_match.group(2)}"

            if not date_iso:
                return None

            # Czyszczenie tytułu ze śmieci marketingowych
            title = re.sub(r"(?i)\\s*-\\s*(bilety|kup|rezerwuj).*$", "", title).strip()

            # Budowa pełnej nazwy i adresu
            full_venue = f"{venue}, {street_address}".strip(", ") if street_address and street_address not in venue else venue
            if not full_venue:
                full_venue = self.canonical_city

            thumb_path = self.save_thumbnail(image_url, title, prefix=f"kupbilecik_{self.city_tag}") if image_url else ""
            unique_url = f"{event_url}#{date_iso}-{time_str.replace(':', '')}"

            return {
                "title": title,
                "date_start": date_iso,
                "time_start": time_str,
                "venue": full_venue,
                "address": f"{full_venue}, {self.canonical_city}".strip(", "),
                "description": description or f"{title} w obiekcie {full_venue}.",
                "image_url": thumb_path or image_url,
                "source_url": unique_url,
                "organizer": "KupBilecik",
                "source": self.source_name,
                "city_tag": self.city_tag
            }

        except Exception as e:
            print(f"[{self.source_name}] Błąd podstrony {event_url}: {e}")
            return None

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        try:
            resp = self.session.get(
                self.events_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=(3.05, 10),
                verify=False
            )
            if resp.status_code != 200:
                return events

            soup = BeautifulSoup(resp.text, "html.parser")
            seen_urls = set()
            urls_to_scrape = []

            for link in soup.select("a[href*='/imprezy/']"):
                href = link.get("href", "").strip()
                if not href or href in ["#", "/"]:
                    continue
                
                full_url = self._format_url(href)
                norm_url = unquote(full_url).lower()
                
                if not any(slug in norm_url for slug in self.required_slugs):
                    continue

                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    urls_to_scrape.append((full_url, link.get_text(strip=True)))

            print(f"[{self.source_name}] Pobieranie szczegółów dla {len(urls_to_scrape)} stron wydarzeń...")
            for full_url, title_fallback in urls_to_scrape:
                ev = self._scrape_detail_page(full_url, title_fallback)
                if ev:
                    events.append(ev)

        except Exception as e:
            print(f"[{self.source_name}] Błąd głównego parsera: {e}")

        print(f"[{self.source_name}] Zakończono. Pobrano {len(events)} zweryfikowanych wydarzeń.")
        return events
"""

scraper_path = Path("src/infrastructure/scrapers/national/kupbilecik_pl.py")
scraper_path.write_text(scraper_code, encoding="utf-8")
print("\n[OK] Zaktualizowano kod w src/infrastructure/scrapers/national/kupbilecik_pl.py")
print("="*60 + "\n")
