import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_enriched.json"
OUTPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_categorized.json"

def apply_6_axis_matrix(item: dict) -> dict:
    name = (item.get("name") or "").lower()
    group = item.get("group") or ""
    amenity = (item.get("raw_amenity") or "").lower()
    wheelchair = item.get("wheelchair")
    is_indoor = item.get("is_indoor", False)
    
    # Domyślny szkielet (Fallback)
    axes = {
        "sub_category": "inne",
        "context": ["dorosli", "solo"],
        "time": ["popoludnie"],
        "weather": "indoor" if is_indoor else "outdoor",
        "season": "caly_rok",
        "accessibility": None
    }

    # -- 1. ZASADY DOSTĘPNOŚCI (ACCESSIBILITY) --
    if wheelchair == "yes":
        axes["accessibility"] = True
    elif wheelchair == "no":
        axes["accessibility"] = False
    elif group in ["natura", "park"]:
        axes["accessibility"] = True  # Parki zazwyczaj są dostępne
    elif "schron" in name or amenity == "bunker":
        axes["accessibility"] = False # Schrony z definicji nie są

    # -- 2. KASKADA KATEGORII (WATERFALL) --
    
    # Gastronomia i Noc
    if any(k in name for k in ["lody", "lodziarnia", "ice cream"]) or amenity == "ice_cream":
        axes.update({"sub_category": "lodziarnia", "context": ["dzieci_mlodsze", "rodzina", "randka"], "season": "lato", "time": ["popoludnie", "wieczor"]})
    elif any(k in name for k in ["kebab", "doner", "burger", "frytki", "fast food"]) or amenity == "fast_food":
        axes.update({"sub_category": "fast_food", "context": ["nastolatki", "znajomi", "solo"], "time": ["popoludnie", "wieczor", "noc"]})
    elif any(k in name for k in ["kawiarnia", "cafe", "kawa", "cukiernia", "mikafka", "mała czarna"]) or amenity == "cafe":
        axes.update({"sub_category": "kawiarnia", "context": ["dorosli", "randka", "solo"], "time": ["poranek", "popoludnie"]})
    elif any(k in name for k in ["pub", "bar", "piwo", "browar", "szkwał"]) or amenity in ["pub", "bar", "biergarten"]:
        axes.update({"sub_category": "bar_pub", "context": ["dorosli", "znajomi"], "time": ["wieczor", "noc"]})
    elif any(k in name for k in ["sushi", "pizzeria", "pizza", "restauracja", "bistro", "obiady", "trattoria"]) or amenity == "restaurant":
        axes.update({"sub_category": "restauracja", "context": ["dorosli", "rodzina", "randka", "znajomi"], "time": ["popoludnie", "wieczor"]})
    
    # Woda i Natura (Sezonowe)
    elif any(k in name for k in ["dębowa", "kąpielisko", "plaża"]) or amenity == "bathing_place":
        axes.update({"sub_category": "akwen", "context": ["dzieci_mlodsze", "nastolatki", "rodzina", "znajomi"], "season": "lato", "time": ["poranek", "popoludnie", "wieczor"], "weather": "outdoor"})
    elif group == "natura" or amenity in ["park", "nature_reserve"]:
        axes.update({"sub_category": "park", "context": ["dzieci_mlodsze", "rodzina", "dorosli"], "time": ["poranek", "popoludnie"], "weather": "outdoor"})
    
    # Sport i Rekreacja
    elif any(k in name for k in ["basen", "pływalnia", "wodnik"]) or amenity in ["swimming_pool", "water_park"]:
        axes.update({"sub_category": "sport_basen", "context": ["dzieci_mlodsze", "nastolatki", "rodzina"], "time": ["poranek", "popoludnie", "wieczor"]})
    elif group == "sport" or amenity in ["sports_centre", "skatepark", "pumptrack"]:
        context = ["nastolatki", "znajomi"] if "skatepark" in name or "pumptrack" in name else ["dorosli", "rodzina"]
        axes.update({"sub_category": "sport_rekreacja", "context": context, "time": ["popoludnie", "wieczor"]})
    
    # Historia, Kultura, Inżynieria
    elif any(k in name for k in ["schron", "blechhammer", "bunker"]) or amenity == "bunker":
        axes.update({"sub_category": "schron_militaria", "context": ["nastolatki", "dorosli", "znajomi"], "time": ["poranek", "popoludnie"]})
    elif any(k in name for k in ["kino", "twierdza"]) or amenity == "cinema":
        axes.update({"sub_category": "kino", "context": ["nastolatki", "rodzina", "randka"], "time": ["popoludnie", "wieczor"], "weather": "indoor"})
    elif any(k in name for k in ["muzeum", "galeria", "izba"]) or amenity in ["museum", "gallery"]:
        axes.update({"sub_category": "muzeum", "context": ["dorosli", "rodzina"], "time": ["poranek", "popoludnie"], "weather": "indoor"})
    elif any(k in name for k in ["dom kultury", "chemik", "mok", "biblioteka"]) or amenity in ["arts_centre", "library"]:
        axes.update({"sub_category": "instytucja_kultury", "context": ["dorosli", "dzieci_mlodsze", "rodzina"], "time": ["popoludnie", "wieczor"], "weather": "indoor"})
    elif any(k in name for k in ["śluza", "syfon", "port", "kanał", "wieża"]) or amenity in ["lock", "water_tower"]:
        axes.update({"sub_category": "inzynieria_wodna", "context": ["dorosli", "rodzina", "solo"], "time": ["poranek", "popoludnie"], "weather": "outdoor"})
    elif any(k in name for k in ["pomnik", "cmentarz", "mauzoleum"]) or amenity in ["memorial", "monument"]:
        axes.update({"sub_category": "miejsce_pamieci", "context": ["dorosli", "solo"], "time": ["poranek", "popoludnie"], "weather": "outdoor"})
    elif group == "historia" or amenity in ["castle", "fort", "ruins"]:
        axes.update({"sub_category": "zabytek", "context": ["dorosli", "rodzina"], "time": ["poranek", "popoludnie"]})

    return axes

def main():
    if not INPUT_FILE.exists():
        print(f"Brak pliku wejściowego: {INPUT_FILE}")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        places = json.load(f)

    categorized_places = []
    stats = {}

    for item in places:
        # Aplikowanie matrycy
        axes = apply_6_axis_matrix(item)
        
        # Przebudowa struktury rekordu
        item["sub_category"] = axes["sub_category"]
        item["tags"] = {
            "context": axes["context"],
            "time": axes["time"],
            "weather": axes["weather"],
            "season": axes["season"],
            "accessibility": axes["accessibility"]
        }
        
        categorized_places.append(item)
        
        sc = axes["sub_category"]
        stats[sc] = stats.get(sc, 0) + 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(categorized_places, f, ensure_ascii=False, indent=2)

    print(f"[OK] Skategoryzowano 6 osiami {len(categorized_places)} obiektów.")
    print("--- STATYSTYKI KATEGORII ---")
    for k, v in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"{k.upper():<20}: {v}")

if __name__ == "__main__":
    main()

