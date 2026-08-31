import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_enriched.json"
OUTPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_categorized.json"

def classify_orthogonal(name: str, group: str, raw_amenity: str):
    n = name.lower()
    a = (raw_amenity or "").lower()

    # Domyślny schemat (fallback)
    result = {
        "sub_category": "inne",
        "tags_context": ["solo"],
        "tags_time": ["popoludnie"],
        "tags_vibe": []
    }

    # Wyjątki - Bar Mleczny (przed zwykłym barem)
    if "bar mleczny" in n:
        return {
            "sub_category": "restauracja",
            "tags_context": ["solo", "rodzina", "znajomi"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["szybko"]
        }

    # Gastronomia
    if any(k in n for k in ["kebab", "doner", "burger", "frytki"]) or a == "fast_food":
        return {
            "sub_category": "fast_food",
            "tags_context": ["solo", "znajomi"],
            "tags_time": ["popoludnie", "wieczor", "noc"],
            "tags_vibe": ["szybko"]
        }
    if any(k in n for k in ["kawiarnia", "cafe", "kawa", "cukiernia", "lody", "mikafka", "mała czarna", "krukafe"]) or a in ["cafe", "ice_cream"]:
        return {
            "sub_category": "kawiarnia",
            "tags_context": ["randka", "solo", "znajomi"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["cicho", "relaks"]
        }
    if any(k in n for k in ["pub", "bar", "piwo", "browar", "szkwał", "street bar"]) or a in ["pub", "bar", "biergarten"]:
        return {
            "sub_category": "bar_pub",
            "tags_context": ["znajomi", "randka"],
            "tags_time": ["wieczor", "noc"],
            "tags_vibe": ["glosno"]
        }
    if any(k in n for k in ["sushi", "pizzeria", "pizza", "restauracja", "bistro", "trattoria", "obiady", "hugo"]) or a == "restaurant":
        return {
            "sub_category": "restauracja",
            "tags_context": ["randka", "rodzina", "znajomi"],
            "tags_time": ["popoludnie", "wieczor"],
            "tags_vibe": ["relaks"]
        }

    # Kultura
    if any(k in n for k in ["kino", "twierdza"]) or a == "cinema":
        return {
            "sub_category": "kino",
            "tags_context": ["randka", "rodzina", "znajomi"],
            "tags_time": ["popoludnie", "wieczor"],
            "tags_vibe": ["kultura", "relaks"]
        }
    if any(k in n for k in ["dom kultury", "chemik", "mok", "kultura", "biblioteka"]) or a in ["arts_centre", "community_centre", "library"]:
        return {
            "sub_category": "instytucja_kultury",
            "tags_context": ["solo", "rodzina"],
            "tags_time": ["poranek", "popoludnie", "wieczor"],
            "tags_vibe": ["kultura", "cicho"]
        }
    if any(k in n for k in ["muzeum", "izba pamięci", "galeria"]) or a in ["museum", "gallery"]:
        return {
            "sub_category": "muzeum",
            "tags_context": ["solo", "rodzina", "znajomi"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["historia", "cicho", "kultura"]
        }

    # Historia i Architektura
    if any(k in n for k in ["schron", "blechhammer", "bunker"]) or a == "bunker":
        return {
            "sub_category": "schron_militaria",
            "tags_context": ["solo", "znajomi"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["historia"]
        }
    if any(k in n for k in ["śluza", "syfon", "port", "kanał", "wieża ciśnień"]) or a in ["lock", "water_tower"]:
        return {
            "sub_category": "inzynieria_wodna",
            "tags_context": ["solo", "randka", "rodzina"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["historia", "natura", "relaks"]
        }
    if any(k in n for k in ["pomnik", "cmentarz", "mauzoleum", "krzyż"]) or a in ["memorial", "monument"]:
        return {
            "sub_category": "miejsce_pamieci",
            "tags_context": ["solo"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["historia", "cicho"]
        }
    if group == "historia" or a in ["castle", "fort", "ruins"]:
        return {
            "sub_category": "zabytek",
            "tags_context": ["solo", "rodzina", "znajomi"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["historia"]
        }

    # Natura i Aktywność
    if any(k in n for k in ["dębowa", "akwen", "jezioro", "kąpielisko", "plaża"]) or a == "bathing_place":
        return {
            "sub_category": "akwen",
            "tags_context": ["randka", "rodzina", "znajomi", "solo"],
            "tags_time": ["poranek", "popoludnie", "wieczor"],
            "tags_vibe": ["natura", "aktywnosc", "relaks"]
        }
    if group == "natura" or a in ["park", "nature_reserve"]:
        return {
            "sub_category": "park",
            "tags_context": ["randka", "rodzina", "solo"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["natura", "cicho", "relaks"]
        }
    if any(k in n for k in ["basen", "pływalnia", "wodnik"]) or a in ["swimming_pool", "water_park"]:
        return {
            "sub_category": "sport_basen",
            "tags_context": ["solo", "rodzina", "znajomi"],
            "tags_time": ["poranek", "popoludnie", "wieczor"],
            "tags_vibe": ["aktywnosc"]
        }
    if group == "sport" or a in ["sports_centre", "skatepark", "pumptrack", "pitch", "kort"]:
        return {
            "sub_category": "sport_rekreacja",
            "tags_context": ["solo", "znajomi"],
            "tags_time": ["poranek", "popoludnie"],
            "tags_vibe": ["aktywnosc", "glosno"]
        }

    return result

def main():
    if not INPUT_FILE.exists():
        print(f"Brak pliku wejściowego: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        places = json.load(f)

    categorized_places = []
    stats_sub_cat = {}

    for item in places:
        name = item.get("name", "").strip()
        group = item.get("group", "")
        raw_amenity = item.get("raw_amenity", "")
        
        classification = classify_orthogonal(name, group, raw_amenity)
        
        # Wstrzyknięcie strukturalnych osi
        item["sub_category"] = classification["sub_category"]
        item["tags"] = {
            "context": classification["tags_context"],
            "time": classification["tags_time"],
            "vibe": classification["tags_vibe"]
        }
        
        categorized_places.append(item)
        
        sc = classification["sub_category"]
        stats_sub_cat[sc] = stats_sub_cat.get(sc, 0) + 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(categorized_places, f, ensure_ascii=False, indent=2)

    print(f"Zakończono kategoryzację {len(categorized_places)} obiektów. Zapisano: {OUTPUT_FILE}")
    print("\nOdrzucone do kategorii 'inne':", stats_sub_cat.get("inne", 0))

if __name__ == "__main__":
    main()
