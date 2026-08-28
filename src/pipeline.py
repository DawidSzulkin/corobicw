import json
import math
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.db import get_active_events, save_event
from src.dedup import process_events
from src.enricher import enrich_missing_descriptions
from src.models import FullEventPage, EventAnalysis, QuickFacts, TicketInfo, NearbyGastro
from src.renderer import HTMLRenderer
from src.scrapers.registry import get_scrapers_for_city

VENUE_MATCH_RULES = {
    "kedzierzyn_kozle": [
        {"keywords": ["parkrun", "bieg parkrun"], "target_id": "kk-park-orderu-usmiechu"},
        {"keywords": ["droga do bullerbyn", "mity i opowie", "mikołajek opowiada", "tajemnicza biblioteka", "brzechw", "zawody marzeń", "oddział dla dzieci", "rynek 3"], "target_id": "kk-mbp-rynek"},
        {"keywords": ["narodowe czytanie", "dyskusyjny klub", "spotkanie autorskie", "wśród zieleni", "mbp", "bibliotek"], "target_id": "kk-mbp-glowna"},
        {"keywords": ["sławięcic", "slawiecic", "plener malarski"], "target_id": "kk-park-slawiecice"},
        {"keywords": ["hotel hugo", "hugo"], "target_id": "kk-hotel-hugo"},
        {"keywords": ["nightskating", "rolkowanie", "śródmieście", "srodmiescie"], "target_id": "kk-hala-srodmiescie"},
        {"keywords": ["hala azoty", "siatkówk", "grand prix", "azoty", "hala widowiskowo-sportowa"], "target_id": "kk-hala-sportowa"},
        {"keywords": ["zamek", "twierdza", "piastowskim", "kozielsk"], "target_id": "kk-zamek-piastowski"},
        {"keywords": ["mzk", "dworzec", "podróżuj z mzk"], "target_id": "kk-dworzec-pkp"},
        {"keywords": ["kameleon", "klub kameleon", "metro", "tomek zdyb"], "target_id": "kk-klub-kameleon"},
        {"keywords": ["chemik", "dk chemik", "kino chemik", "mok", "coverowe", "sklep z facetami", "siesta w drodze", "gala fado", "dżem session", "dewódzki", "najdroższy", "strauss", "sylwestrowa"], "target_id": "kk-chemik"},
        {"keywords": ["lech", "dk lech", "blachownia"], "target_id": "kk-lech"}
    ],
    "bielsko_biala": [
        {"keywords": ["cavatina", "cavatina hall"], "target_id": "bb-cavatina-hall"},
        {"keywords": ["bck", "bielskie centrum kultury", "dom muzyki", "festiwal kompozytorów"], "target_id": "bb-bck"},
        {"keywords": ["plac teatralny", "teatr polski", "teatru polskiego", "duża scena tp", "carmen", "sąsiedzi z góry", "testosteron", "tina", "viva maria", "wanda"], "target_id": "bb-teatr-polski"},
        {"keywords": ["banialuka", "teatr lalek", "calineczka", "kamyk i księżyc", "mały książę", "królowa śniegu", "włosy mamy", "zagubiony chłopiec", "urodziny w nigdylandii", "narodziny", "tuwim i"], "target_id": "bb-teatr-banialuka"},
        {"keywords": ["galeria bielska", "galeria bwa", "bwa", "momenty graniczne", "dziadostwo", "święto lasu", "bojdys", "street artu", "wariacje goldbergowskie", "mazolewski"], "target_id": "bb-galeria-bielska-bwa"},
        {"keywords": ["zamek", "sułkowskich", "muzeum historyczne"], "target_id": "bb-zamek-sulkowskich"},
        {"keywords": ["spartan", "karate", "dębowiec", "debowiec", "hala pod dębowcem", "hala pod debowcem", "bbosir"], "target_id": "bb-hala-pod-debowcem"},
        {"keywords": ["rudeboy", "rudeboy club", "illusion", "hostia", "iron head", "closterkeller"], "target_id": "bb-rudeboy-club"}
    ]
}

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def slugify(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L").replace("ó", "o").replace("Ó", "O")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)

MOJIBAKE_PATTERN = re.compile(
    r"(�|&#65533;|Ä…|Ä‡|Ä™|Å‚|Å„|Ã³|Å›|Åº|Å¼|Ä„|Ä†|Ä˜|Å|Åƒ|Ã“|Åš|Å¹|Å»|Ãł|Åş|Åź|ÃŠ|[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{2,}\?[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{2,})"
)

def assert_clean_utf8(text: str, context: str = "") -> str:
    if not text:
        return ""
    m = MOJIBAKE_PATTERN.search(text)
    if m:
        raise ValueError(
            f"[BŁĄD KODOWANIA UTF-8] Wykryto uszkodzony fragment '{m.group()}' w polu: '{context}'.\n"
            f"Pełna wartość: {text[:160]}"
        )
    return text

def _sanitize_llm_string(val: Any, context: str = "") -> str:
    if not val:
        return ""
    val = str(val).strip()
    val = re.sub(r"^np\.\s*", "", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*lub Całodniowe", "", val, flags=re.IGNORECASE)
    val = val.strip()
    return assert_clean_utf8(val, context)

def _get_geo_coords(place: Dict[str, Any]) -> Optional[tuple[float, float]]:
    geo = place.get("geo") if isinstance(place.get("geo"), dict) else {}
    coords = place.get("coordinates") if isinstance(place.get("coordinates"), dict) else {}
    lat = geo.get("lat") or coords.get("lat") or place.get("lat")
    lon = geo.get("lon") or coords.get("lon") or place.get("lon")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (ValueError, TypeError):
            return None
    return None

def _load_places_index(city_tag: str) -> Dict[str, Dict[str, Any]]:
    norm_tag = city_tag.replace("-", "_")
    city_file = Path(f"data/{norm_tag}/places_clean.json")
    if not city_file.exists():
        city_file = Path("places_clean.json")

    if city_file.exists():
        try:
            with open(city_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {
                        item.get("place_id") or item.get("id") or f"idx-{i}": item
                        for i, item in enumerate(data)
                    }
        except Exception as err:
            print(f"[ERROR] Błąd ładowania pliku miejsc {city_file}: {err}")
            return {}
    return {}

def _find_nearest_gastro(venue_place: Optional[Dict[str, Any]], all_places: Dict[str, Dict[str, Any]]) -> List[NearbyGastro]:
    if not venue_place:
        return []

    v_coords = _get_geo_coords(venue_place)
    if not v_coords:
        return []

    v_lat, v_lon = v_coords
    candidates = []

    NON_GASTRO = ["biblioteka", "teatr", "szkoła", "hala", "muzeum", "zamek", "kościół", "ośrodek", "dom kultury"]
    GASTRO_KEYS = ["kawiarnia", "restauracja", "bistro", "kebab", "pizza", "burger", "pub", "gastronomia", "cukiernia", "bar "]

    venue_id = venue_place.get("place_id") or venue_place.get("id")

    for p_id, p in all_places.items():
        if p_id == venue_id or p.get("place_id") == venue_id or p.get("id") == venue_id:
            continue

        cat = str(p.get("category") or p.get("group") or p.get("raw_amenity") or "").lower()
        name = str(p.get("name", "")).lower()

        if any(nk in name or nk in cat for nk in NON_GASTRO):
            continue

        if any(gk in cat or gk in name for gk in GASTRO_KEYS) or name.startswith("bar ") or p.get("group") == "gastronomia":
            candidates.append(p)

    scored = []
    for c in candidates:
        c_coords = _get_geo_coords(c)
        if c_coords:
            c_lat, c_lon = c_coords
            dist = int(haversine(v_lat, v_lon, c_lat, c_lon))
            if dist <= 1500:  # Maksymalnie 1.5 km spaceru
                walk_time = max(1, round(dist / 80))
                scored.append((dist, walk_time, c))

    scored.sort(key=lambda x: x[0])

    gastro_items: List[NearbyGastro] = []
    for dist, walk_time, c in scored[:2]:
        category_name = c.get("category") or c.get("raw_amenity") or "Gastronomia"
        gastro_items.append(NearbyGastro(
            place_id=c.get("place_id") or c.get("id", ""),
            name=_sanitize_llm_string(c.get("name", "")),
            distance_m=dist,
            walk_time_min=walk_time,
            category=_sanitize_llm_string(category_name)
        ))

    return gastro_items

def _resolve_place(event: Dict[str, Any], places_by_id: Dict[str, Dict[str, Any]], city_tag: str) -> Optional[Dict[str, Any]]:
    norm_tag = city_tag.replace("-", "_")
    assigned_id = event.get("place_id") or event.get("venue_id")
    if assigned_id and assigned_id in places_by_id:
        return places_by_id[assigned_id]

    text = f"{event.get('title', '')} {event.get('description', '')} {event.get('venue', '')} {event.get('analysis', {}).get('ticket_info', {}).get('venue_name', '')}".lower()
    rules = VENUE_MATCH_RULES.get(norm_tag, [])
    for rule in rules:
        if any(kw in text for kw in rule["keywords"]):
            target_id = rule.get("target_id")
            if target_id and target_id in places_by_id:
                return places_by_id[target_id]
            for p_id, p_data in places_by_id.items():
                p_name = p_data.get("name", "").lower()
                if any(tk in p_name for tk in rule.get("target_keywords", [])):
                    return p_data
    return None

def _prepare_event_models(events: List[Any], city_tag: str, city_name: str, places_by_id: Dict[str, Dict[str, Any]]) -> List[FullEventPage]:
    models: List[FullEventPage] = []

    for e in events:
        if not isinstance(e, dict):
            continue

        title = _sanitize_llm_string(e.get("title", ""))
        date_start = str(e.get("date_start", e.get("date", ""))).strip()[:10]
        date_end = str(e.get("date_end", date_start)).strip()[:10]
        date_formatted = e.get("date_formatted") or date_start
        source_url = e.get("source_url") or e.get("url") or ""
        thumb_url = e.get("thumbnail_url") or e.get("image_url") or "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&q=80"
        slug = slugify(e.get("slug") or f"{date_start}-{title}")
        analysis_raw = e.get("analysis") or {}

        matched_place = _resolve_place(e, places_by_id, city_tag=city_tag)
        resolved_place_id = (matched_place.get("place_id") or matched_place.get("id")) if matched_place else None

        if matched_place:
            venue_name = _sanitize_llm_string(matched_place.get("name", "Obiekt Miejski"))
            addr_obj = matched_place.get("address") if isinstance(matched_place.get("address"), dict) else {}
            street = _sanitize_llm_string(addr_obj.get("street") or matched_place.get("street", ""))
            house = _sanitize_llm_string(addr_obj.get("housenumber") or matched_place.get("housenumber", ""))
            place_city = _sanitize_llm_string(addr_obj.get("city") or matched_place.get("city") or city_name)

            address = f"ul. {street} {house}, {place_city}".strip(" ,") if street else place_city

            parking_details = matched_place.get("logistics", {}).get("parking_details", [])
            nearest_p = matched_place.get("nearest_parking")

            if parking_details:
                top_p = parking_details[0]
                fee = _sanitize_llm_string(top_p.get("fee_label", "Parking"))
                st = _sanitize_llm_string(top_p.get("street", "w pobliżu"))
                parking_str = f"{fee} ({top_p.get('distance_m', 0)}m, ul. {st})"
            elif nearest_p:
                dist_m = nearest_p.get("distance_m", 50)
                fee_txt = "Płatny parking" if nearest_p.get("is_fee") else "Bezpłatny parking"
                parking_str = f"{fee_txt} (~{dist_m}m)"
            else:
                parking_str = "Dostępny w strefie miejskiej"
        else:
            venue_name = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("venue_name") or e.get("venue") or "Wydarzenie")
            address = _sanitize_llm_string(analysis_raw.get("address") or e.get("address") or city_name)
            parking_str = "Parking ogólnodostępny w pobliżu obiektu"

        category = _sanitize_llm_string(analysis_raw.get("category") or e.get("category") or "Kultura i Rozrywka")
        organizer = _sanitize_llm_string(analysis_raw.get("organizer") or e.get("source") or venue_name)
        lead = _sanitize_llm_string(analysis_raw.get("editorial_lead") or e.get("description", "")[:180] or (title + "."))
        full_desc = _sanitize_llm_string(analysis_raw.get("full_description") or e.get("description") or lead)
        raw_b = analysis_raw.get("details_bullets") or []
        bullets = [_sanitize_llm_string(b) for b in raw_b if _sanitize_llm_string(b) and _sanitize_llm_string(b).lower() != title.lower()]
        badges = [_sanitize_llm_string(b) for b in analysis_raw.get("badges", [category]) if "np." not in b.lower()]
        if not badges:
            badges = [category]

        time_start = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("time_start") or e.get("time_start") or "18:00")
        doors_open = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("doors_open", ""))
        price_range = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("price_range") or e.get("price_range") or "Sprawdź bilety")

        nearby_gastro = _find_nearest_gastro(matched_place, places_by_id)

        event_obj = FullEventPage(
            slug=slug,
            title=title,
            date_start=date_start,
            date_end=date_end,
            date_formatted=date_formatted,
            image_url=thumb_url,
            source_url=source_url,
            place_id=resolved_place_id,
            nearby_gastro=nearby_gastro,
            analysis=EventAnalysis(
                category=category,
                badges=badges,
                organizer=organizer,
                editorial_lead=lead,
                full_description=full_desc,
                details_bullets=bullets,
                quick_facts=QuickFacts(
                    duration=_sanitize_llm_string(analysis_raw.get("quick_facts", {}).get("duration", "~2h")),
                    age_rating=_sanitize_llm_string(analysis_raw.get("quick_facts", {}).get("age_rating", "Wszyscy")),
                    parking=parking_str
                ),
                ticket_info=TicketInfo(
                    time_start=time_start,
                    doors_open=doors_open if doors_open else None,
                    venue_name=venue_name,
                    price_range=price_range,
                    place_id=resolved_place_id
                ),
                address=address
            )
        )
        models.append(event_obj)

    models.sort(key=lambda x: x.date_start)
    return models

def run_city_pipeline(
    city_cfg: Dict[str, Any],
    renderer: HTMLRenderer,
    output_dir: str = "public",
    render_only: bool = False,
    source_filter: Optional[str] = None,
    skip_enrich: bool = False
) -> None:
    raw_tag = city_cfg.get("city_tag", "").strip()
    city_name = city_cfg.get("city", "").strip()
    partner_id = city_cfg.get("partner_id", "")
    today_iso = datetime.now().strftime("%Y-%m-%d")

    db_tags = [raw_tag, raw_tag.replace("-", "_"), raw_tag.replace("_", "-")]
    places_by_id = _load_places_index(raw_tag)

    print(f"\n==========================================")
    print(f"  URUCHAMIANIE PIPELINE: {city_name.upper()} ({raw_tag})")
    print(f"==========================================")

    if render_only:
        raw_events = []
        for tag in set(db_tags):
            found = get_active_events(city_tag=tag, min_date=today_iso)
            if found:
                raw_events.extend(found)

        seen = set()
        unique_events = []
        for ev in raw_events:
            k = (ev.get("title", ""), ev.get("date_start", ev.get("date", "")))
            if k not in seen:
                seen.add(k)
                unique_events.append(ev)

        if not unique_events:
            print(f"[RENDERER] Brak aktywnych wydarzeń w bazie dla '{raw_tag}'.")
            return

        event_models = _prepare_event_models(unique_events, city_tag=raw_tag, city_name=city_name, places_by_id=places_by_id)
        renderer.render_city(
            city_name=city_name,
            city_tag=raw_tag,
            events=event_models,
            places=places_by_id,
            output_dir=output_dir
        )
        return

    scrapers = get_scrapers_for_city(raw_tag, partner_id=partner_id)
    if source_filter:
        scrapers = [s for s in scrapers if s.source_name.lower() == source_filter.lower()]

    raw_events = []
    for scraper in scrapers:
        try:
            items = scraper.fetch_events()
            for it in items:
                it["city_tag"] = raw_tag
            raw_events.extend(items)
        except Exception as e:
            print(f"[{scraper.source_name}] Błąd scrapera: {e}")

    deduped = process_events(raw_events)
    for ev in deduped:
        save_event(city_tag=raw_tag, event_data=ev)

    if not skip_enrich:
        enrich_missing_descriptions(city_tag=raw_tag)

    active_db_events = get_active_events(city_tag=raw_tag, min_date=today_iso)
    event_models = _prepare_event_models(active_db_events, city_tag=raw_tag, city_name=city_name, places_by_id=places_by_id)
    renderer.render_city(
        city_name=city_name,
        city_tag=raw_tag,
        events=event_models,
        places=places_by_id,
        output_dir=output_dir
    )