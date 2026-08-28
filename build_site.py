import json
import logging
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

RAW_EVENTS_FILE = Path("data/raw/kedzierzyn_kozle_latest.json")
PLACES_FILE = Path("places_clean.json")
OUTPUT_DIR = Path("public")
TEMPLATES_DIR = Path("templates")

CITIES_CONFIG = [
    {"name": "Kędzierzyn-Koźle", "tag": "kedzierzyn-kozle"}
]

VENUE_MATCH_RULES = [
    {"keywords": ["parkrun", "bieg parkrun"], "target_keywords": ["park miejski", "miejski", "pojednania"]},
    {"keywords": ["dk chemik", "chemik", "dom kultury chemik"], "target_keywords": ["chemik"]},
    {"keywords": ["dk lech", "dom kultury lech", "lech blachownia"], "target_keywords": ["lech"]},
    {"keywords": ["muzeum ziemi kozielskiej", "zamek w koźlu", "twierdza"], "target_keywords": ["muzeum", "kozielsk"]},
    {"keywords": ["hala azoty", "azoty", "siatkówk", "grand prix", "mosir"], "target_keywords": ["azoty", "mosir", "hala"]},
    {"keywords": ["filia nr 1", "słowackiego"], "target_keywords": ["filia nr 1"]},
    {"keywords": ["filia nr 4", "wyzwolenia"], "target_keywords": ["filia nr 4"]},
    {"keywords": ["filia nr 5", "damrota"], "target_keywords": ["filia nr 5"]},
]

def slugify(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L").replace("ó", "o").replace("Ó", "O")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)

def find_best_place_match(event: dict, places: list) -> dict:
    text = f"{event.get('title', '')} {event.get('description', '')}".lower()
    for rule in VENUE_MATCH_RULES:
        if any(kw in text for kw in rule["keywords"]):
            for p in places:
                p_name = p.get("name", "").lower()
                if any(tk in p_name for tk in rule["target_keywords"]):
                    return p
    return None

def build_site():
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    
    hub_template = env.get_template("portal_hub.html")
    home_template = env.get_template("home.html")
    event_template = env.get_template("event_page.html")

    places = []
    if PLACES_FILE.exists():
        with open(PLACES_FILE, "r", encoding="utf-8") as f:
            places = json.load(f)
            
    raw_events = []
    if RAW_EVENTS_FILE.exists():
        with open(RAW_EVENTS_FILE, "r", encoding="utf-8") as f:
            raw_events = json.load(f)

    today_str = datetime.now().strftime("%Y-%m-%d")
    jinja_events = []

    for ev in raw_events:
        date = str(ev.get("date", ""))[:10]
        
        # TWARDY FILTR: Odrzucanie wydarzeń z przeszłości
        if date < today_str:
            continue

        place = find_best_place_match(ev, places)
        if not place:
            continue
            
        title = ev.get("title", "").strip()
        slug = f"{date}-{slugify(title)}"
        
        parking_str = "Brak dedykowanego parkingu"
        parking_details = place.get("logistics", {}).get("parking_details", [])
        if parking_details:
            p_top = parking_details[0]
            parking_str = f"{p_top['fee_label']} parking ({p_top['distance_m']}m)"

        street = place.get("street", "")
        house = place.get("housenumber", "")
        address_str = f"ul. {street} {house}, Kędzierzyn-Koźle".strip(" ,")
        
        rich_event = {
            "slug": slug,
            "title": title,
            "date_start": date,
            "date_end": date, 
            "date_formatted": date,
            "source_url": ev.get("url", ""),
            "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&q=80",
            "thumbnail_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400&q=80",
            "analysis": {
                "category": place.get("category", "Rozrywka"),
                "organizer": ev.get("source", "Organizator Lokalny"),
                "badges": ["Nadchodzące", "Potwierdzone"],
                "editorial_lead": ev.get("description", "").strip() or f"Wydarzenie zlokalizowane w: {place['name']}.",
                "full_description": ev.get("description", "").strip() or "Brak szczegółowego opisu wydarzenia.",
                "details_bullets": ["Wejście od głównej ulicy", f"Dostępność: {place.get('wheelchair', 'Brak danych')}"],
                "address": address_str,
                "quick_facts": {
                    "duration": "~2h",
                    "age_rating": "Brak ograniczeń",
                    "parking": parking_str
                },
                "ticket_info": {
                    "venue_name": place["name"],
                    "time_start": "09:00" if "parkrun" in title.lower() else "18:00",
                    "doors_open": "08:45" if "parkrun" in title.lower() else "17:30",
                    "price_range": "Wstęp bezpłatny" if "parkrun" in title.lower() else "Sprawdź u organizatora"
                }
            }
        }
        jinja_events.append(rich_event)

    jinja_events.sort(key=lambda x: x["date_start"])

    # 1. Hub Główny
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(hub_template.render(cities=CITIES_CONFIG))

    # 2. Przygotowanie czystego katalogu wydarzeń
    city_dir = OUTPUT_DIR / CITIES_CONFIG[0]["tag"]
    events_dir = city_dir / "wydarzenia"
    if events_dir.exists():
        shutil.rmtree(events_dir)
    events_dir.mkdir(parents=True, exist_ok=True)

    # 3. Agenda Miasta
    with open(city_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(home_template.render(city=CITIES_CONFIG[0]["name"], events=jinja_events))

    # 4. Podstrony wydarzeń
    for ev in jinja_events:
        event_folder = events_dir / ev["slug"]
        event_folder.mkdir(parents=True, exist_ok=True)
        with open(event_folder / "index.html", "w", encoding="utf-8") as f:
            f.write(event_template.render(city=CITIES_CONFIG[0]["name"], event=ev))

    logging.info("Wygenerowano %d aktywnych, przyszłych wydarzeń w SSG.", len(jinja_events))

if __name__ == "__main__":
    build_site()
