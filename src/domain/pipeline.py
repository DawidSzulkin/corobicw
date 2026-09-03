
def _clean_ticket_url(url: str) -> str:
    if not url:
        return ""
    u = url.split("#")[0].strip()
    parsed = urllib.parse.urlparse(u)
    if not parsed.query:
        return u
    qs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    clean_qs = [(k, v) for k, v in qs if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "_ga")]
    new_query = urllib.parse.urlencode(clean_qs)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))

def _get_url_priority(url: str, organizer: str = "") -> tuple[int, str]:
    prio, name, _ = resolve_ticket_provider(url, organizer)
    return (prio, name)

from src.utils.helpers import haversine, slugify, resolve_ticket_provider
import json
import os
import re
import unicodedata
import urllib.parse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import concurrent.futures
from difflib import SequenceMatcher

from src.infrastructure.db import sync_city_events, get_active_events, save_events_batch, DB_PATH, purge_expired_events
from src.core.models import FullEventPage, EventAnalysis, QuickFacts, TicketInfo, NearbyGastro, TicketOffer
from src.infrastructure.renderer import HTMLRenderer
from src.infrastructure.scrapers.registry import get_scrapers_for_city
from src.normalizer import normalize_ticket_price, format_polish_date


MOJIBAKE_PATTERN = re.compile(
    r"(&#65533;|\?+|[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{2,}\?[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{2,})"
)

STOPWORDS = {
    "im", "imienia", "w", "i", "oraz", "na", "z", "ze", "do", "al", "aleja",
    "ul", "ulica", "plac", "pl", "godz", "godzina", "sala", "scena", "duza", 
    "kameralna", "widowiskowa", "bilety", "bilet", "kup", "koncert", "spektakl", 
    "wydarzenie", "standup", "kabaret", "trasa", "program", "nowy", "live", "tour"
}

GENERIC_VENUE_TERMS = {
    "miejsce", "sala", "klub", "centrum", "teatr", "kawiarnia", "restauracja",
    "pub", "park", "plac", "hala", "dom", "osrodek", "ośrodek", "scena",
    "galeria", "filharmonia", "kino", "studio", "foyer", "kameralna"
}

GENERIC_VENUE_WORDS = {
    "teatr", "centrum", "dom", "kultura", "kultury", "galeria", "muzeum",
    "osrodek", "hala", "klub", "szkola", "biblioteka", "filharmonia", "arena"
}

def assert_clean_utf8(text: str, context: str = "") -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = MOJIBAKE_PATTERN.sub("", text)
    return text.strip()

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
            if dist <= 1500:  
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

def _normalize_tokens(text: str, city_tag: str = "") -> List[str]:
    if not text:
        return []
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8').lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    city_stops = set()
    if city_tag:
        base_parts = city_tag.replace("-", "_").split("_")
        for b in base_parts:
            city_stops.update([
                b, b + "u", b + "e", b + "a", b + "ie", b + "em", 
                b + "ski", b + "ska", b + "skie", b + "skiej", b + "skim", b + "skich"
            ])
            
    return [t for t in text.split() if t and t not in STOPWORDS and t not in city_stops and len(t) > 1]

def _generate_acronym(tokens: List[str]) -> str:
    return "".join([t[0] for t in tokens]) if len(tokens) >= 2 else ""

def _calculate_place_similarity(query_text: str, place_name: str, city_tag: str = "") -> float:
    q_tokens = _normalize_tokens(query_text, city_tag=city_tag)
    p_tokens = _normalize_tokens(place_name, city_tag=city_tag)
    if not q_tokens or not p_tokens:
        return 0.0

    q_set = set(q_tokens)
    p_set = set(p_tokens)

    if len(p_tokens) == 1 and len(p_tokens[0]) <= 3:
        return 0.95 if p_tokens[0] in q_set else 0.0

    p_distinct = [t for t in p_tokens if t not in GENERIC_VENUE_WORDS]
    q_distinct = [t for t in q_tokens if t not in GENERIC_VENUE_WORDS]

    p_meaningful = [t for t in p_distinct if t.lower() not in GENERIC_VENUE_TERMS and len(t) > 2]
    q_meaningful = [t for t in q_distinct if t.lower() not in GENERIC_VENUE_TERMS and len(t) > 2]

    if p_meaningful and all(t in q_set for t in p_meaningful):
        matched_ratio = len(p_meaningful) / max(len(p_tokens), 1)
        return 0.90 + (0.09 * matched_ratio)

    if q_meaningful and all(t in p_set for t in q_meaningful):
        matched_ratio = len(q_meaningful) / max(len(p_meaningful), 1)
        return 0.85 + (0.10 * matched_ratio)

    p_acronym = _generate_acronym(p_tokens)
    if len(p_acronym) >= 3 and p_acronym in q_set:
        return 0.92

    p_acronym_dist = _generate_acronym(p_distinct)
    if len(p_acronym_dist) >= 2 and p_acronym_dist in q_set:
        return 0.88

    q_sorted = " ".join(sorted(q_tokens))
    p_sorted = " ".join(sorted(p_tokens))
    
    if p_sorted == q_sorted:
        return 0.95
    if len(p_tokens) >= 2 and p_sorted in q_sorted:
        return 0.86

    intersection = len(p_set & q_set)
    union = len(p_set | q_set)
    jaccard = intersection / union if union > 0 else 0
    seq_ratio = SequenceMatcher(None, p_sorted, q_sorted).ratio()
    
    distinct_score = 0.0
    if p_distinct:
        matches = 0
        for pt in p_distinct:
            if pt in q_set:
                matches += 1
            elif len(pt) >= 4:
                for qt in q_distinct:
                    if abs(len(pt) - len(qt)) <= 2 and pt[0] == qt[0]:
                        if SequenceMatcher(None, pt, qt).ratio() >= 0.85:
                            matches += 1
                            break
        distinct_score = (matches / len(p_distinct)) * 0.85

    return max(jaccard, seq_ratio * 0.80, distinct_score)

def _resolve_place(event: Dict[str, Any], places_by_id: Dict[str, Dict[str, Any]], city_cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_v = str(event.get("venue", "")).strip().lower()
    c_name = city_cfg.get("city", "").strip().lower()
    if raw_v in [c_name, city_cfg.get("city_tag", ""), "obiekt widowiskowy", "wydarzenie"]:
        event["venue"] = ""

    assigned_id = event.get("place_id") or event.get("venue_id")
    if assigned_id and assigned_id in places_by_id:
        return places_by_id[assigned_id]

    city_tag = city_cfg.get("city_tag", "")

    text = f"{event.get('title', '')} {event.get('description', '')} {event.get('venue', '')} {event.get('analysis', {}).get('ticket_info', {}).get('venue_name', '')}".lower()
    for rule in city_cfg.get("venue_match_rules", []):
        if any(kw in text for kw in rule.get("keywords", [])):
            target_id = rule.get("target_id")
            if target_id and target_id in places_by_id:
                return places_by_id[target_id]
            for p_id, p_data in places_by_id.items():
                p_name = p_data.get("name", "").lower()
                if any(tk in p_name for tk in rule.get("target_keywords", [])):
                    return p_data

    venue_specific = f"{event.get('venue', '')} {event.get('analysis', {}).get('ticket_info', {}).get('venue_name', '')}".strip()
    search_corpus = venue_specific if len(venue_specific) > 3 and "[brak" not in venue_specific.lower() else f"{event.get('title', '')} {event.get('description', '')[:120]}"

    best_place = None
    best_score = 0.0

    for p_id, p_data in places_by_id.items():
        place_name = p_data.get("name", "")
        if not place_name:
            continue
        
        score = _calculate_place_similarity(search_corpus, place_name, city_tag=city_tag)
        if score > best_score:
            best_score = score
            best_place = p_data

    if best_score >= 0.75:
        return best_place

    return None

def _clean_event_title(title: str, city_name: str = "") -> str:
    """Usuwa śmieci SEO, nazwy miast, obiektów i daty doklejone do tytułu."""
    if not title:
        return "Wydarzenie"
    t = title.strip()
    t = re.split(r'\s*-\s*(?:Opole|Bielsko|Kędzierzyn|Bilety|Kup|Amfiteatr|NCPP|NCK|MOK|Dom Kultury|\d{1,2}\s+[a-ząćęłńóśźż]+).*$', t, flags=re.IGNORECASE)[0]
    t = re.split(r'\s*\|\s*.*$', t)[0]
    t = re.sub(r'\s*\([^)]*(?:Narodowe|Centrum|Amfiteatr|Kultury|Piosenki)[^)]*\)', '', t, flags=re.IGNORECASE)
    t = re.sub(r',\s*\d{1,2}\s+[a-ząćęłńóśźż]+.*$', '', t, flags=re.IGNORECASE)
    return t.strip(" -:,")

GENERIC_STOPWORDS = {
    "przy", "swiecach", "świecach", "koncert", "spektakl", "recital",
    "festiwal", "festival", "stand", "standup", "stand-up", "show",
    "muzyka", "muzyki", "polska", "polskiej", "bielsko", "biala",
    "bielsku", "bialej", "opole", "opolu", "live", "tour", "trasa",
    "nowy", "program", "wieczor", "wieczór", "kameralny", "akustycznie",
    "bilety", "kup", "dla", "oraz", "jego", "orzeł", "orlem", "orłem",
    "sala", "redutowa", "domu", "kultury", "bck", "cavatina", "hall",
    "żywo", "zywo"
}

def _stem_pl(w: str) -> str:
    """Ucina typowe polskie końcówki fleksyjne dla bezpiecznego porównywania rdzeni."""
    w = w.lower().strip()
    for suffix in ["ego", "emu", "ach", "ami", "ych", "ich", "iej", "owi", "em", "om", "ie", "ce", "ek", "ka", "ki", "ku", "ów", "u", "a", "e", "y", "i", "o", "ą", "ę"]:
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[:-len(suffix)]
    return w

def _are_titles_duplicate(t1: str, t2: str, time1: str = "", time2: str = "") -> bool:
    """Weryfikuje duplikaty uwzględniając fleksję, stopwords i przesunięcia czasowe."""
    if time1 and time2 and time1 != time2 and ":" in time1 and ":" in time2:
        try:
            h1, m1 = map(int, time1.split(":")[:2])
            h2, m2 = map(int, time2.split(":")[:2])
            if abs((h1 * 60 + m1) - (h2 * 60 + m2)) >= 45:
                return False
        except Exception:
            pass

    import re
    from difflib import SequenceMatcher

    # 1. Sprawdzenie surowego podobieństwa całych ciągów
    if SequenceMatcher(None, t1.lower().strip(), t2.lower().strip()).ratio() >= 0.80:
        return True

    # 2. Ekstrakcja i stemming tokenów
    raw1 = re.findall(r'[a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}', t1.lower())
    raw2 = re.findall(r'[a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}', t2.lower())

    stems1 = {_stem_pl(w) for w in raw1}
    stems2 = {_stem_pl(w) for w in raw2}
    
    stop_stems = {_stem_pl(w) for w in GENERIC_STOPWORDS}
    content1 = {s for s in stems1 if s not in stop_stems}
    content2 = {s for s in stems2 if s not in stop_stems}

    # Fallback jeśli tytuł składał się wyłącznie ze stopwords
    s1 = content1 if content1 else stems1
    s2 = content2 if content2 else stems2

    if not s1 or not s2:
        return False

    intersection = s1 & s2
    union = s1 | s2
    jaccard = len(intersection) / len(union) if union else 0.0

    if jaccard >= 0.40:
        return True

    if s1.issubset(s2) or s2.issubset(s1):
        return True

    return SequenceMatcher(None, " ".join(sorted(stems1)), " ".join(sorted(stems2))).ratio() >= 0.75

def sanitize_price(price_str: str, provider: str) -> str:
    if not price_str:
        return "Sprawdź dostępność"
    p = price_str.strip()
    p = re.sub(r"\s*\([^)]*\)", "", p).strip()
    p_low = p.lower()
    if any(free_w in p_low for free_w in ["wstęp wolny", "wstep wolny", "bezpłatn", "bezplatn", "za darmo", "wstęp darmowy", "brak opłat"]):
        return "Wstęp wolny"
    if p_low in ["bilety płatne", "płatne", "bilet", "kup bilet"]:
        return "Sprawdź dostępność"
    return p

def extract_numeric_price(p_str: str) -> float:
    p_low = (p_str or "").lower()
    if any(free_w in p_low for free_w in ["wstęp wolny", "wstep wolny", "bezpłatn", "za darmo"]):
        return 0.0
    match = re.search(r"(\d+(?:[.,]\d+)?)", p_str.replace(" ", ""))
    if match:
        return float(match.group(1).replace(",", "."))
    return float("inf")

def _deduplicate_ticket_offers_list(offers: list, fallback_url: str = "", fallback_price: str = "") -> list:
    grouped = {}
    
    for off in (offers or []):
        u = (off.get("url") or "").strip()
        if not u:
            continue
        prio, prov = _get_url_priority(u)
        clean_u = _clean_ticket_url(u)
        raw_p = off.get("price") or fallback_price or ""
        sanitized_p = sanitize_price(raw_p, prov)
        
        domain = urllib.parse.urlparse(clean_u).netloc.lower()
        key = prov if prov not in ("Organizator", "Strona źródłowa", "Inne") else f"{prov}:{domain}"
        
        if key not in grouped:
            grouped[key] = {
                "provider": prov,
                "url": clean_u,
                "price": sanitized_p,
                "raw_price": raw_p,
                "is_primary": off.get("is_primary", False),
                "discounts": off.get("discounts") or []
            }
        else:
            if grouped[key]["price"] == "Sprawdź dostępność" and sanitized_p != "Sprawdź dostępność":
                grouped[key]["price"] = sanitized_p
                grouped[key]["url"] = clean_u
            if off.get("discounts") and not grouped[key].get("discounts"):
                grouped[key]["discounts"] = off.get("discounts")
                
    if not grouped and fallback_url:
        prio, prov = _get_url_priority(fallback_url)
        clean_u = _clean_ticket_url(fallback_url)
        grouped[prov] = {
            "provider": prov,
            "url": clean_u,
            "price": sanitize_price(fallback_price, prov),
            "raw_price": fallback_price,
            "is_primary": True,
            "discounts": []
        }
        
    deduped = list(grouped.values())
    deduped.sort(key=lambda x: (extract_numeric_price(x["price"]), -_get_url_priority(x["url"])[0]))
    
    paid_nums = [extract_numeric_price(o["price"]) for o in deduped if 0 < extract_numeric_price(o["price"]) < float("inf")]
    min_paid = min(paid_nums) if paid_nums else float("inf")
    
    for idx, o in enumerate(deduped):
        o["is_primary"] = (idx == 0)
        o["tag"] = None
        o["tag_class"] = None
        
        u_low = o["url"].lower()
        prov_low = o["provider"].lower()
        num_p = extract_numeric_price(o["price"])
        is_free = ("wolny" in o["price"].lower() or "bezpłat" in o["price"].lower() or num_p == 0.0)
        
        # Dla wydarzeń darmowych: zerujemy zniżki i tagi
        if is_free:
            o["discounts"] = []
            o["tag"] = None
            o["tag_class"] = None
        else:
            _, _, is_off = resolve_ticket_provider(o["url"], o["provider"])
            o["is_official"] = is_off
            if is_off:
                o["official_badge"] = "Oficjalna kasa"
                
            if num_p < float("inf") and num_p == min_paid and len(deduped) > 1:
                o["tag"] = "Najlepsza cena"
                o["tag_class"] = "best-price"
            elif is_off:
                o["tag"] = "Oficjalna kasa"
                o["tag_class"] = "official"
            # Zniżki zostają dokładnie takie, jakie dostarczył scraper (bez sztywnego mocka!)
            
    return deduped

def deduplicate_events(events: list, city_name: str = "") -> list:
    by_date = {}
    for ev in events:
        d = str(ev.get("date_start", ev.get("date", "")))[:10]
        by_date.setdefault(d, []).append(ev)
    
    merged_results = []
    for d, day_events in by_date.items():
        clusters = []
        for ev in day_events:
            ev_title = _clean_event_title(ev.get("title", ""), city_name)
            ev["title"] = ev_title
            ev_time = str(ev.get("time_start", "")).strip()
            
            matched_cluster = None
            for cluster in clusters:
                if any(_are_titles_duplicate(ev_title, c_ev.get("title", ""), ev_time, str(c_ev.get("time_start", "")).strip()) for c_ev in cluster):
                    matched_cluster = cluster
                    break
            if matched_cluster is not None:
                matched_cluster.append(ev)
            else:
                clusters.append([ev])
        
        for cluster in clusters:
            if len(cluster) == 1:
                single = dict(cluster[0])
                u = single.get("source_url") or single.get("url") or ""
                offers = single.get("ticket_offers") or []
                pr = single.get("price_range") or single.get("price") or ""
                single["ticket_offers"] = _deduplicate_ticket_offers_list(offers, u, pr)
                if single["ticket_offers"]:
                    single["source_url"] = single["ticket_offers"][0]["url"]

                merged_results.append(single)
                continue
            
            best_title = max([c.get("title", "") for c in cluster if c.get("title")], key=len)
            
            desc_candidates = [
                c.get("description") or (c.get("analysis", {}).get("full_description") if isinstance(c.get("analysis"), dict) else "") or ""
                for c in cluster
            ]
            best_desc = max(desc_candidates, key=len) if desc_candidates else ""
            
            best_img = ""
            for c in cluster:
                img = c.get("image_url") or c.get("thumbnail_url", "")
                if "/assets/thumbnails/" in str(img):
                    best_img = img
                    break
                elif img and not best_img:
                    best_img = img
            
            best_venue = ""
            best_place_id = None
            best_address = ""
            for c in cluster:
                p_id = c.get("place_id") or (c.get("analysis", {}).get("ticket_info", {}).get("place_id") if isinstance(c.get("analysis"), dict) else None)
                if p_id:
                    best_place_id = p_id
                    best_venue = c.get("venue") or c.get("analysis", {}).get("ticket_info", {}).get("venue_name", "")
                    best_address = c.get("address", "")
                    break
            
            if not best_venue:
                best_venue = cluster[0].get("venue", "")
                best_address = cluster[0].get("address", "")
            
            candidate_offers = []
            for c in cluster:
                for off in (c.get('ticket_offers') or []):
                    if isinstance(off, dict) and off.get('url'):
                        candidate_offers.append(off)
                c_url = (c.get('source_url') or c.get('url') or '').strip()
                if c_url:
                    candidate_offers.append({
                        'url': c_url,
                        'price': c.get('price_range') or c.get('price') or '',
                        'is_primary': False
                    })

            fallback_u = cluster[0].get("source_url") or cluster[0].get("url") or ""
            fallback_p = cluster[0].get("price_range") or cluster[0].get("price") or ""
            ranked_offers = _deduplicate_ticket_offers_list(candidate_offers, fallback_u, fallback_p)

            primary_url = ranked_offers[0]["url"] if ranked_offers else fallback_u
            primary_price = ranked_offers[0]["price"] if ranked_offers else fallback_p

            primary = dict(cluster[0])
            best_img = ""
            best_discounts = []
            for c in cluster:
                img = c.get("image_url") or c.get("thumbnail_url", "")
                if "/assets/thumbnails/" in str(img):
                    best_img = img
                elif img and not best_img:
                    best_img = img
                
                disc = c.get("discounts")
                if disc and isinstance(disc, list) and len(disc) > len(best_discounts):
                    best_discounts = disc

            primary = dict(cluster[0])
            primary["title"] = best_title
            primary["image_url"] = best_img
            primary["discounts"] = best_discounts if best_discounts else primary.get("discounts")
            if best_desc:
                primary["description"] = best_desc
                if isinstance(primary.get("analysis"), dict):
                    primary["analysis"]["full_description"] = best_desc
            primary["image_url"] = best_img
            if best_place_id:
                primary["place_id"] = best_place_id
            if best_venue:
                primary["venue"] = best_venue
            if best_address:
                primary["address"] = best_address
            primary["source_url"] = primary_url
            if primary_price:
                primary["price_range"] = primary_price
            primary["ticket_offers"] = ranked_offers
            
            merged_results.append(primary)
            
    return merged_results

def _generate_event_slug(title: str, date_start: str, time_start: str, seen_slugs: set) -> str:
    base = slugify(title) or "wydarzenie"
    clean_date = date_start.strip()[:10]
    candidate = f"{base}-{clean_date}" if clean_date else base
    
    if candidate not in seen_slugs:
        seen_slugs.add(candidate)
        return candidate
    
    clean_time = time_start.replace(":", "").strip() if time_start else ""
    time_candidate = f"{candidate}-{clean_time}" if clean_time else candidate
    if time_candidate not in seen_slugs:
        seen_slugs.add(time_candidate)
        return time_candidate

    idx = 2
    while f"{candidate}-{idx}" in seen_slugs:
        idx += 1
    final_slug = f"{candidate}-{idx}"
    seen_slugs.add(final_slug)
    return final_slug


def _format_address(raw_addr: Any, default_city: str = "") -> str:
    if isinstance(raw_addr, dict):
        street = str(raw_addr.get("street", "")).strip()
        postal = str(raw_addr.get("postal_code", "")).strip()
        city = str(raw_addr.get("city", default_city)).strip()
        parts = [p for p in [street, postal, city] if p]
        return ", ".join(parts) if parts else default_city
    if isinstance(raw_addr, str):
        return raw_addr.strip() or default_city
    return default_city


    def _prepare_event_models(self, enriched_events: list) -> list:
        models = []
        for e in enriched_events:
            if not isinstance(e, dict):
                continue
            s_u = (e.get('source_url') or e.get('url') or '').strip()
            s_p = (e.get('price_range') or e.get('price') or '').strip()
            raw_offers = e.get('ticket_offers') or []
            if not raw_offers and s_u:
                raw_offers = _deduplicate_ticket_offers_list([], fallback_url=s_u, fallback_price=s_p)

            parsed_offers = []
            for o in raw_offers:
                if isinstance(o, dict) and o.get('url'):
                    parsed_offers.append(TicketOffer(
                        provider=o.get('provider', 'Bilety'),
                        url=o.get('url', ''),
                        price=o.get('price'),
                        is_primary=o.get('is_primary', False),
                        tag=o.get('tag'),
                        tag_class=o.get('tag_class'),
                        is_official=o.get('is_official', False),
                        official_badge=o.get('official_badge'),
                        discounts=o.get('discounts') or []
                    ))
                elif isinstance(o, TicketOffer):
                    parsed_offers.append(o)

            # Utworzenie EventModel
            e_copy = dict(e)
            e_copy['ticket_offers'] = parsed_offers
            try:
                models.append(EventModel(**e_copy))
            except Exception:
                # Jeśli EventModel ma ścisłe pola, przekazujemy klucze
                models.append(EventModel(
                    id=e.get('id', ''),
                    title=e.get('title', ''),
                    slug=e.get('slug', ''),
                    city_tag=e.get('city_tag', ''),
                    date_start=e.get('date_start', ''),
                    date_end=e.get('date_end', ''),
                    time_start=e.get('time_start', ''),
                    venue=e.get('venue', ''),
                    address=e.get('address', ''),
                    price_range=e.get('price_range', ''),
                    description=e.get('description', ''),
                    image_url=e.get('image_url', ''),
                    source_url=s_u,
                    source=e.get('source', ''),
                    organizer=e.get('organizer', ''),
                    ticket_offers=parsed_offers,
                    analysis=e.get('analysis')
                ))
        return models
def _prepare_full_event_pages(
    events: list, places_by_id: dict, city_cfg: dict, city_name: str
) -> List[FullEventPage]:
    models: List[FullEventPage] = []
    seen_slugs: set = set()
    city_tag = city_cfg.get("city_tag", "").strip()

    for e in events:
        if isinstance(e, FullEventPage):
            models.append(e)
            continue
            
        title = _clean_event_title(e.get("title", ""), city_name)
        if not title:
            continue
            
        date_start = str(e.get("date_start") or e.get("date") or "")[:10]
        if not date_start:
            continue
            
        date_end = str(e.get("date_end") or date_start)[:10]
        image_url = e.get("image_url") or e.get("thumbnail_url") or ""
        source_url = e.get("source_url") or e.get("url") or ""
        
        analysis_raw = e.get("analysis") if isinstance(e.get("analysis"), dict) else {}
        time_start = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("time_start") or e.get("time_start") or "18:00")
        slug = _generate_event_slug(title, date_start, time_start, seen_slugs)
        
        matched_place = _resolve_place(e, places_by_id, city_cfg)
        resolved_pid = ((matched_place.get("place_id") or matched_place.get("id") or matched_place.get("slug")) if matched_place else None) or e.get("place_id") or analysis_raw.get("ticket_info", {}).get("place_id")
        
        if matched_place:
            venue_name = _sanitize_llm_string(matched_place.get("name", "Wydarzenie"))
            address_val = _format_address(matched_place.get("address"), default_city=city_name)
            parking_details = matched_place.get("parking_details", [])
            nearest_p = matched_place.get("nearest_parking", {})
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
            raw_addr = analysis_raw.get("address") or e.get("address")
            address_val = _format_address(raw_addr, default_city=city_name)
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

        doors_open = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("doors_open", ""))
        raw_price_str = _sanitize_llm_string(analysis_raw.get("ticket_info", {}).get("price_range") or e.get("price_range") or "")
        is_free_flag = analysis_raw.get("ticket_info", {}).get("is_free") if analysis_raw.get("ticket_info", {}).get("is_free") is not None else e.get("is_free")
        price_range = normalize_ticket_price(raw_price_str, is_free_flag=is_free_flag, source_url=source_url)
        date_formatted = format_polish_date(date_start)

        nearby_gastro = _find_nearest_gastro(matched_place, places_by_id)

                # Mapowanie ticket_offers (Record Merge)
        raw_offers = e.get("ticket_offers") or []
        if not raw_offers:
            s_u = (e.get("source_url") or e.get("url") or "").strip()
            s_p = (e.get("price_range") or e.get("price") or "").strip()
            if s_u:
                raw_offers = _deduplicate_ticket_offers_list([], fallback_url=s_u, fallback_price=s_p)
        else:
            # Upewnij się, że oferty przejdą normalizację tagów (Najlepsza cena / Oficjalna kasa)
            raw_offers = _deduplicate_ticket_offers_list(raw_offers)

        parsed_offers = []
        for o in raw_offers:
            if isinstance(o, dict) and o.get("url"):
                parsed_offers.append(TicketOffer(
                    provider=o.get("provider", "Bilety"),
                    url=o.get("url", ""),
                    price=o.get("price"),
                    is_primary=o.get("is_primary", False),
                    tag=o.get("tag"),
                    tag_class=o.get("tag_class"),
                    is_official=o.get('is_official', False),
                    official_badge=o.get('official_badge'),
                    discounts=o.get("discounts") or []
                ))
            elif isinstance(o, TicketOffer):
                parsed_offers.append(o)

        # Detekcja stanu odwołania wydarzenia
        price_check = (raw_price_str or "").lower()
        title_check = title.lower()
        offers_check = any("odwo" in (o.get("price") or "").lower() or "cancel" in (o.get("price") or "").lower() for o in (e.get("ticket_offers") or []))
        is_cancelled_flag = bool(
            "odwo" in price_check or "cancel" in price_check or
            "odwo" in title_check or "cancel" in title_check or
            offers_check or e.get("status") == "cancelled"
        )

        quick_facts = QuickFacts(
            duration=_sanitize_llm_string(analysis_raw.get("quick_facts", {}).get("duration", "~2h")),
            age_rating=_sanitize_llm_string(analysis_raw.get("quick_facts", {}).get("age_rating", "Wszyscy")),
            parking=parking_str
        )

        ticket_info = TicketInfo(
            time_start=time_start,
            venue_name=venue_name,
            price_range=price_range,
            doors_open=doors_open if doors_open else None,
            place_id=resolved_pid
        )

        analysis_obj = EventAnalysis(
            category=category,
            badges=badges,
            organizer=organizer,
            editorial_lead=lead,
            full_description=full_desc,
            details_bullets=bullets,
            quick_facts=quick_facts,
            ticket_info=ticket_info,
            address=address_val
        )

        discounts_val = e.get("discounts") or []

        event_obj = FullEventPage(
            slug=slug,
            title=title,
            date_start=date_start,
            date_end=date_end,
            date_formatted=date_formatted,
            image_url=image_url,
            source_url=source_url,
            place_id=resolved_pid,
            analysis=analysis_obj,
            nearby_gastro=nearby_gastro,
            ticket_offers=parsed_offers,
            discounts=discounts_val,
            is_cancelled=is_cancelled_flag
        )
        models.append(event_obj)

    models.sort(key=lambda x: x.date_start)
    return models

def run_city_pipeline(
    city_cfg: Dict[str, Any],
    renderer: HTMLRenderer,
    output_dir: str = "public",
    render_only: bool = False,
    source_filter: Optional[str] = None
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

    try:
        deleted = purge_expired_events(raw_tag)
        if deleted > 0:
            print(f"[DB] Twarde czyszczenie: usunięto {deleted} przeterminowanych wydarzeń przed startem potoku.")
    except Exception as e:
        print(f"[DB WARN] Nie udało się wykonać czyszczenia: {e}")

    if render_only:
        raw_events = []
        for tag in set(db_tags):
            found = get_active_events(city_tag=tag, min_date=today_iso)
            if found:
                raw_events.extend(found)

        unique_events = deduplicate_events(raw_events, city_name=city_name)

        if not unique_events:
            print(f"[RENDERER] Brak aktywnych wydarzeń w bazie dla '{raw_tag}'.")
            return

        event_models = _prepare_full_event_pages(unique_events, places_by_id=places_by_id, city_cfg=city_cfg, city_name=city_name)
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
    
    def fetch_from_scraper(scraper):
        try:
            items = scraper.fetch_events()
            for it in items:
                it["city_tag"] = raw_tag
            return items
        except Exception as e:
            print(f"[{scraper.source_name}] Błąd scrapera: {e}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_from_scraper, scrapers)
        for items in results:
            raw_events.extend(items)

    save_events_batch(city_tag=raw_tag, events=raw_events)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, payload FROM events WHERE city_tag = ?", (raw_tag,))
        for ev_id, p_json in cursor.fetchall():
            p_data = json.loads(p_json)
            matched = _resolve_place(p_data, places_by_id, city_cfg)
            if matched:
                pid = matched.get("place_id") or matched.get("id")
                p_data["place_id"] = pid
                if "analysis" not in p_data: p_data["analysis"] = {}
                if "ticket_info" not in p_data["analysis"]: p_data["analysis"]["ticket_info"] = {}
                p_data["analysis"]["ticket_info"]["place_id"] = pid
                p_data["analysis"]["ticket_info"]["venue_name"] = matched.get("name")
                cursor.execute("UPDATE events SET payload = ? WHERE id = ?", (json.dumps(p_data, ensure_ascii=False), ev_id))
        conn.commit()


    active_db_events = get_active_events(city_tag=raw_tag, min_date=today_iso)
    deduped_events = deduplicate_events(active_db_events, city_name=city_name)
    sync_city_events(raw_tag, deduped_events)
    event_models = _prepare_full_event_pages(deduped_events, places_by_id=places_by_id, city_cfg=city_cfg, city_name=city_name)
    renderer.render_city(
        city_name=city_name,
        city_tag=raw_tag,
        events=event_models,
        places=places_by_id,
        output_dir=output_dir
    )