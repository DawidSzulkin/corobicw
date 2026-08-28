import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_enriched.json"
OUTPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_final.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

SYSTEM_PROMPT = """Jesteś surowym redaktorem przewodnika po Kędzierzynie-Koźlu. 
Na podstawie przekazanych danych o obiekcie zwróć WYŁĄCZNIE poprawny JSON (bez znaczników markdown, bez ```json):
{
  "display_name": "Elegancka, pełna nazwa własna miejsca",
  "sub_category": "Jedna z: [restauracja, kawiarnia, bar_pub, fast_food, kino, teatr, dom_kultury, muzeum, zabytek, schron_militaria, inzynieria_wodna, park, akwen, sport_basen, sport_rekreacja]",
  "editorial_lead": "2 zwarte, konkretne zdania o klimacie i specyfice miejsca. Zero banałów typu 'warto odwiedzić to malownicze miejsce'.",
  "insider_tip": "1 konkretna wskazówka (np. czego spróbować, kiedy przyjść, na co uważać).",
  "vibe_tags": ["2-4 tagi z: randka, rodzina_dzieci, szybki_lunch, praca_zdalna, piwo_wieczor, historia, relaks_cisza, aktywnosc_sport"]
}"""

def call_ollama(prompt_text: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt_text,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        raw_response = res.get("response", "{}").strip()
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
        return json.loads(raw_response.strip())

def main():
    if not INPUT_FILE.exists():
        print(f"[BŁĄD] Brak pliku wejściowego: {INPUT_FILE}")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        places = json.load(f)

    processed = {}
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                processed = {p["id"]: p for p in saved}
                print(f"[INFO] Znaleziono zapisany stan: {len(processed)} przetworzonych obiektów.")
        except Exception:
            pass

    print(f"[START] Przetwarzanie {len(places)} obiektów przez model '{OLLAMA_MODEL}'...")

    total = len(places)
    for idx, item in enumerate(places, 1):
        item_id = item["id"]
        if item_id in processed:
            continue

        addr = item.get("address", {})
        street = addr.get("street") or ""
        nr = addr.get("housenumber") or ""
        district = addr.get("district") or ""
        
        raw_context = {
            "nazwa_raw": item.get("name"),
            "grupa": item.get("group"),
            "typ_obiektu": item.get("raw_amenity"),
            "lokalizacja": f"{street} {nr} ({district}), Kędzierzyn-Koźle".strip(),
            "cechy": {
                "darmowe": item.get("is_free"),
                "pod_dachem": item.get("is_indoor"),
                "godziny": item.get("opening_hours")
            }
        }

        prompt = f"Opisz ten obiekt:\n{json.dumps(raw_context, ensure_ascii=False, indent=2)}"

        try:
            t0 = time.time()
            ai_data = call_ollama(prompt)
            dt = round(time.time() - t0, 1)

            item["display_name"] = ai_data.get("display_name", item.get("name"))
            item["sub_category"] = ai_data.get("sub_category", "inne")
            item["editorial"] = {
                "lead": ai_data.get("editorial_lead", ""),
                "insider_tip": ai_data.get("insider_tip", "")
            }
            item["vibe_tags"] = ai_data.get("vibe_tags", [])

            processed[item_id] = item
            print(f"[{idx}/{total}] ({dt}s) {item['display_name']} -> [{item['sub_category']}] {item['vibe_tags']}")

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(list(processed.values()), f, ensure_ascii=False, indent=2)

        except urllib.error.URLError:
            print("\n[BŁĄD] Brak łączności z Ollamą na porcie 11434.")
            sys.exit(1)
        except Exception as e:
            print(f"[{idx}/{total}] [OSTRZEŻENIE] Błąd dla {item.get('name')}: {e}")
            item["display_name"] = item.get("name")
            item["sub_category"] = "inne"
            item["editorial"] = {"lead": "", "insider_tip": ""}
            item["vibe_tags"] = []
            processed[item_id] = item

    print(f"\n[SUKCES] Zakończono! Wyniki zapisano w: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
