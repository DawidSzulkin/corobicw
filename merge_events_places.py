import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import unicodedata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

RAW_EVENTS_FILE = Path("data/raw/kedzierzyn_kozle_latest.json")
PLACES_FILE = Path("places_clean.json")
CITY_SLUG = "kedzierzyn-kozle"

VENUE_MATCH_RULES = [
    {
        "keywords": ["parkrun", "bieg parkrun"],
        "target_keywords": ["park miejski", "miejski", "pojednania"],
    },
    {
        "keywords": ["dk chemik", "chemik", "dom kultury chemik"],
        "target_keywords": ["chemik"],
    },
    {
        "keywords": ["dk lech", "dom kultury lech", "lech blachownia"],
        "target_keywords": ["lech"],
    },
    {
        "keywords": ["muzeum ziemi kozielskiej", "zamek w koźlu", "baszta", "twierdza koźle"],
        "target_keywords": ["muzeum", "kozielsk"],
    },
    {
        "keywords": ["hala azoty", "azoty", "siatkówk", "grand prix", "mosir"],
        "target_keywords": ["azoty", "mosir", "hala"],
    },
    {
        "keywords": ["filia nr 1", "słowackiego"],
        "target_keywords": ["filia nr 1"],
    },
    {
        "keywords": ["filia nr 4", "wyzwolenia"],
        "target_keywords": ["filia nr 4"],
    },
    {
        "keywords": ["filia nr 5", "damrota"],
        "target_keywords": ["filia nr 5"],
    },
]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)


def find_best_place_match(event: Dict[str, Any], places: List[Dict[str, Any]]) -> Optional[str]:
    text = f"{event.get('title', '')} {event.get('description', '')}".lower()

    for rule in VENUE_MATCH_RULES:
        if any(kw in text for kw in rule["keywords"]):
            for p in places:
                p_name = p.get("name", "").lower()
                if any(tk in p_name for tk in rule["target_keywords"]):
                    return p["id"]

    best_id = None
    max_len = 0
    for p in places:
        p_name = p.get("name", "").lower()
        if len(p_name) > 5 and p_name in text:
            if len(p_name) > max_len:
                max_len = len(p_name)
                best_id = p["id"]

    return best_id


def run_integration():
    with open(PLACES_FILE, "r", encoding="utf-8") as f:
        places = json.load(f)

    with open(RAW_EVENTS_FILE, "r", encoding="utf-8") as f:
        events = json.load(f)

    for p in places:
        p["upcoming_events"] = []

    matched_count = 0

    for ev in events:
        matched_id = find_best_place_match(ev, places)
        if matched_id:
            matched_count += 1
            title = ev.get("title", "").strip()
            date = str(ev.get("date", ""))[:10]
            slug = f"{date}-{slugify(title)}"
            
            event_dto = {
                "slug": slug,
                "title": title,
                "date": date,
                "source_url": ev.get("url", ""),
                "description": ev.get("description", "").strip() or f"Wydarzenie: {title} w Kędzierzynie-Koźlu."
            }

            for p in places:
                if p["id"] == matched_id:
                    if not any(e["slug"] == slug for e in p["upcoming_events"]):
                        p["upcoming_events"].append(event_dto)

    for p in places:
        p["upcoming_events"].sort(key=lambda x: x["date"])

    places.sort(key=lambda x: len(x["upcoming_events"]), reverse=True)

    with open(PLACES_FILE, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

    logging.info("Zintegrowano %d wydarzeń z miejscami.", matched_count)


if __name__ == "__main__":
    run_integration()
