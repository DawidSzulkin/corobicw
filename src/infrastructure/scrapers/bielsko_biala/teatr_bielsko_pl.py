import re
import urllib3
from datetime import datetime
from typing import Any, Dict, List, Set, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from bs4 import BeautifulSoup
from src.infrastructure.scrapers.base import BaseScraper
from src.infrastructure.scrapers.contracts import ShowContract

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TeatrBielskoPlScraper(BaseScraper):
    """
    Scraper Teatru Polskiego w Bielsku-Białej integrujący API repertuaru,
    podstrony spektakli oraz deterministyczny kontrakt dostępności architektonicznej.
    """

    BOX_OFFICE_PHONE = "33 822 84 53"
    STAGE_SPECS = {
        "duża scena": {
            "wheelchair": True,
            "hearing_loop": True
        },
        "mała scena": {
            "wheelchair": False,
            "hearing_loop": False
        }
    }

    def __init__(self, city_tag: str = "bielsko_biala"):
        super().__init__(
            source_name="teatr_bielsko_pl",
            base_url="https://teatr.bielsko.pl"
        )
        self.city_tag = city_tag
        self.api_url = f"{self.base_url}/api/repertoire"
        self.seen_signatures: Set[str] = set()
        self.shows_cache: Dict[str, Dict[str, Any]] = {}
        self.default_og_image = "https://teatr.bielsko.pl/ogimage.jpg"
        self.boilerplate_keywords = [
            "cookies", "polityk", "mailing", "kasa biletowa",
            "dofinansowan", "teatr polski ul.", "zastrzega",
            "specjalne podzi", "bardzo dziękujemy", "partner spektaklu"
        ]

    def _parse_datetime(self, iso_str: str) -> tuple[str, str]:
        if not iso_str:
            return "", "Według harmonogramu"
        try:
            clean_iso = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_iso)
            if ZoneInfo and dt.tzinfo:
                dt = dt.astimezone(ZoneInfo("Europe/Warsaw"))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except Exception:
            date_part = iso_str[:10] if len(iso_str) >= 10 else ""
            time_part = iso_str[11:16] if len(iso_str) >= 16 else "Według harmonogramu"
            return date_part, time_part

    def _parse_line_pair(self, raw_txt: str) -> tuple[str, str]:
        """Rozdziela rolę od wykonawcy, chroniąc myślniki instrumentów orkiestry."""
        txt = raw_txt.strip()
        if re.search(r"\s+[\u2013\u2014]\s+", txt):
            parts = re.split(r"\s+[\u2013\u2014]\s+", txt, maxsplit=1)
        elif " - " in txt:
            parts = txt.rsplit(" - ", 1)
        else:
            return "Występuje", txt

        role = parts[0].strip()
        person = parts[1].strip()

        if role.lower().startswith("muzyk - "):
            instrument = role[8:].strip()
            role = f"Muzyk ({instrument})"

        return role, person

    def _parse_duration_and_interval(self, raw_text: str) -> tuple[str, str]:
        """Rozdziela czysty czas trwania od liczby przerw."""
        if not raw_text:
            return "Brak danych", "Brak"

        m_dur = re.search(r"(\d+\s*(?:min|minut))", raw_text, re.I)
        dur = m_dur.group(1).strip() if m_dur else "Brak danych"

        m_int = re.search(r"\((\d+\s*przerw[a-y]?)\)", raw_text, re.I)
        interval = m_int.group(1).strip() if m_int else "Brak"
        return dur, interval

    def _fetch_show_details(self, slug: str, title: str) -> Dict[str, Any]:
        if not slug:
            thumb = self.save_thumbnail(self.default_og_image, title, prefix="teatrbielsko")
            return {
                "duration_str": None,
                "interval_str": "Brak",
                "premiere_date": None,
                "age_limit": None,
                "warnings": [],
                "description_story": f"Spektakl {title} w Teatrze Polskim w Bielsku-Białej.",
                "creators": [],
                "cast": [],
                "image_url": thumb or self.default_og_image
            }

        if slug in self.shows_cache:
            return self.shows_cache[slug]

        raw_dur = ""
        premiere_date = None
        age_limit = None
        warnings = []
        creators = []
        cast = []
        story_paras = []
        poster_url = ""

        try:
            url = f"{self.base_url}/spektakl/{slug}"
            resp = self.session.get(
                url,
                headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
                timeout=(4.0, 10.0),
                verify=False
            )
            resp.encoding = "utf-8"

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                full_text = soup.get_text(" ", strip=True)

                # 1. Czas trwania i przerwa
                dur_h2 = soup.find(lambda el: el.name in ["h2", "h3"] and "czas trwania" in el.get_text().lower())
                if dur_h2 and dur_h2.parent:
                    p_dur = dur_h2.parent.find("p")
                    if p_dur:
                        raw_dur = p_dur.get_text(strip=True)
                if not raw_dur:
                    m = re.search(r"\d+\s*min(?:\s*\([^)]+\))?", resp.text)
                    if m:
                        raw_dur = m.group(0)

                # 2. Premiera spektaklu
                prem_h2 = soup.find(lambda el: el.name in ["h2", "h3", "div"] and "premiera" in el.get_text().lower())
                if prem_h2 and prem_h2.parent:
                    m = re.search(r"\d{2}\.\d{2}\.\d{4}", prem_h2.parent.get_text())
                    if m:
                        premiere_date = m.group(0)

                # 3. Ograniczenia wiekowe (twarde granice słów)
                if re.search(r"\b(?:tylko\s+dla\s+dorosłych|od\s+18\s*lat)\b", full_text, re.I):
                    age_limit = "18+"
                elif re.search(r"\b(?:od\s+16\s*lat|dla\s+widzów\s+od\s+16)\b", full_text, re.I):
                    age_limit = "16+"
                elif re.search(r"\b(?:dla\s+dzieci|spektakl\s+familijny)\b", full_text, re.I):
                    age_limit = "Dla dzieci"

                # 4. Triggery sensoryczne
                if re.search(r"\b(?:stroboskop(?:y|owe)?|światł[ao]\s+stroboskop)\b", full_text, re.I):
                    warnings.append("światła stroboskopowe")
                if re.search(r"\b(?:używane\s+są\s+dymy|efekty\s+dymne|w\s+spektaklu\s+używane\s+są\s+dymy)\b", full_text, re.I):
                    warnings.append("dym sceniczny")
                if re.search(r"\b(?:wulgaryzm(?:y)?|wulgarny\s+język)\b", full_text, re.I):
                    warnings.append("dosadny język")
                if re.search(r"\b(?:wystrzał(?:y)?|efekty\s+hukowe)\b", full_text, re.I):
                    warnings.append("efekty hukowe / wystrzały")

                # 5. Twórcy
                tw_h2 = soup.find(lambda el: el.name in ["h2", "h3"] and "twórc" in el.get_text().lower())
                if tw_h2 and tw_h2.parent:
                    ul = tw_h2.parent.find("ul") or tw_h2.find_next_sibling("ul")
                    if ul:
                        for li in ul.find_all("li"):
                            r, p = self._parse_line_pair(li.get_text(" ", strip=True))
                            creators.append({"role": r, "name": p})

                # 6. Obsada
                ob_h2 = soup.find(lambda el: el.name in ["h2", "h3"] and "obsad" in el.get_text().lower())
                if ob_h2 and ob_h2.parent:
                    ul = ob_h2.parent.find("ul") or ob_h2.find_next_sibling("ul")
                    if ul:
                        for li in ul.find_all("li"):
                            r, p = self._parse_line_pair(li.get_text(" ", strip=True))
                            cast.append({"character": r, "actor": p})

                # 7. Czysty opis
                for p in soup.find_all("p"):
                    if p.find_parent(["li", "ul", "footer", "nav"]):
                        continue
                    txt = p.get_text(" ", strip=True)
                    txt_low = txt.lower()
                    if len(txt) >= 60 and not any(bp in txt_low for bp in self.boilerplate_keywords):
                        if not any(sw in txt_low for sw in ["autor –", "reżyseria –", "premiera:", "ostrzeżenia:"]):
                            story_paras.append(txt)

                # 8. Plakat
                og_img = soup.find("meta", property="og:image")
                if og_img and og_img.get("content") and "ogimage" not in og_img["content"].lower():
                    poster_url = og_img["content"]

                if not poster_url:
                    cdn_imgs = soup.find_all("img", src=re.compile(r"/uploads/.*\.(?:jpg|jpeg|png|webp)", re.IGNORECASE))
                    if cdn_imgs:
                        raw_src = cdn_imgs[0]["src"]
                        poster_url = f"{self.base_url}{raw_src}" if raw_src.startswith("/") else raw_src

        except Exception as e:
            print(f"[{self.source_name}] Błąd podstrony /spektakl/{slug}: {e}")

        if not poster_url:
            poster_url = self.default_og_image

        dur_str, int_str = self._parse_duration_and_interval(raw_dur)
        thumb = self.save_thumbnail(poster_url, title, prefix="teatrbielsko")
        final_img = thumb or poster_url

        cached_data = {
            "duration_str": dur_str,
            "interval_str": int_str,
            "premiere_date": premiere_date,
            "age_limit": age_limit,
            "warnings": warnings,
            "description_story": "\n\n".join(story_paras) if story_paras else "",
            "creators": creators,
            "cast": cast,
            "image_url": final_img
        }
        self.shows_cache[slug] = cached_data
        return cached_data

    def fetch_events(self) -> List[Dict[str, Any]]:
        events = []
        today_iso = datetime.now().strftime("%Y-%m-%d")
        self.seen_signatures.clear()

        print(f"\n[{self.source_name}] Pobieranie repertuaru Teatru Polskiego w Bielsku-Białej...")

        try:
            resp = self.session.get(self.api_url, timeout=(4.0, 12.0), verify=False)
            if resp.status_code != 200:
                print(f"[{self.source_name}] Błąd HTTP API: {resp.status_code}")
                return events

            data = resp.json()
            raw_items = data.get("events", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            for item in raw_items:
                if not isinstance(item, dict) or item.get("hiddenFromRepertoire"):
                    continue

                show_event = item.get("showEvent") or {}
                raw_title = item.get("title") or show_event.get("title", "")
                title = re.sub(r"\s+", " ", str(raw_title).replace("\xa0", " ")).strip()
                if not title:
                    continue

                raw_date = item.get("date", "")
                date_str, time_str = self._parse_datetime(raw_date)

                if not date_str or date_str < today_iso:
                    continue

                raw_stage = item.get("stage", {})
                stage_name = raw_stage.get("name", "").strip() if isinstance(raw_stage, dict) else "Duża Scena"

                sig = f"{date_str}_{time_str}_{stage_name}_{title.lower()}"
                if sig in self.seen_signatures:
                    continue
                self.seen_signatures.add(sig)

                slug = show_event.get("slug", "")
                event_url = f"{self.base_url}/spektakl/{slug}" if slug else f"{self.base_url}/repertuar"

                details = self._fetch_show_details(slug, title)

                # Dostępność sali ze słownika
                stage_key = stage_name.lower()
                specs = self.STAGE_SPECS.get(stage_key, {"wheelchair": False, "hearing_loop": False})

                # Status biletów
                free_seats = item.get("freeSeats")
                status = item.get("status")
                if free_seats == 0 or status == "sold_out":
                    price_info = "Bilety wyprzedane"
                else:
                    price_info = "Bilety płatne (Kasa / Online)"

                contract = ShowContract(
                    title=title,
                    date_start=date_str,
                    time_start=time_str,
                    source_url=event_url,
                    source=self.source_name,
                    venue="Teatr Polski w Bielsku-Białej",
                    stage_name=stage_name,
                    address="ul. 1 Maja 1, Bielsko-Biała",
                    city=self.city_tag,
                    wheelchair_accessible=specs["wheelchair"],
                    hearing_loop=specs["hearing_loop"],
                    box_office_phone=self.BOX_OFFICE_PHONE,
                    duration_str=details.get("duration_str"),
                    interval_str=details.get("interval_str", "Brak"),
                    premiere_date=details.get("premiere_date"),
                    age_limit=details.get("age_limit"),
                    warnings=details.get("warnings", []),
                    description=details.get("description_story", ""),
                    image_url=details.get("image_url"),
                    price_range=price_info,
                    creators=details.get("creators", []),
                    cast=details.get("cast", [])
                )

                events.append(contract.to_dict())

        except Exception as e:
            print(f"[{self.source_name}] Błąd główny fetch_events: {e}")

        sold_out = sum(1 for e in events if e.get("price_range") == "Bilety wyprzedane")
        print(f"[{self.source_name}] Pomyślnie zmapowano {len(events)} terminów do ShowContract (wyprzedane: {sold_out}, w cache: {len(self.shows_cache)}).")
        return events
