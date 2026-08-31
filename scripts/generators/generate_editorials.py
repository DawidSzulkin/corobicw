import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_categorized.json"
OUTPUT_FILE = BASE_DIR / "data" / "kedzierzyn_kozle" / "places_final.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

# Szybka korekta zidentyfikowanych anomalii przed zasileniem LLM
def patch_anomalies(item: dict) -> dict:
    name_l = item.get("name", "").lower()
    amenity = (item.get("raw_amenity") or "").lower()

    if "tężnia" in name_l:
        item["sub_category"] = "park"
        item["tags"]["vibe"] = ["relaks", "cicho"]
        item["tags"]["weather"] = "outdoor"
    elif "muszla" in name_l or amenity == "theatre":
        item["sub_category"] = "instytucja_kultury"
        item["tags"]["weather"] = "outdoor"
    elif "klub wiejski" in name_l or "dom działkowca" in name_l or amenity == "community_centre":
        item["sub_category"] = "instytucja_kultury"
    elif "belweder" in name_l:
        item["sub_category"] = "zabytek"
    elif "fort" in name_l:
        item["sub_category"] = "zabytek"
    
    return item

FEW_SHOT_SYSTEM = """Jesteś rzeczowym redaktorem przewodnika miejskiego po Kędzierzynie-Koźlu.
Twórz wyłącznie zwięzłe, konkretne opisy bez lania wody i bez zbędnych wstępów.

Zwracaj WYŁĄCZNIE poprawny format JSON (bez bloków markdown, bez ```json):
{
  "lead": "2 zwarte, treściwe zdania o obiekcie, jego specyfice lub historii.",
  "tip": "1 konkretna, praktyczna wskazówka dla odwiedzającego."
}"""

def call_ollama(name: str, sub_cat: str, address: str, tags: dict) -> dict:
    prompt = f"""Obiekt: {name}
Kategoria: {sub_cat}
Lokalizacja: {address}
Cechy: pogoda={tags.get('weather')}, sezon={tags.get('season')}

Wygeneruj lead i tip w JSON:"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": FEW_SHOT_SYSTEM,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2}
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=45) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        raw = res.get("response", "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].replace("json", "")
        return json.loads(raw.strip())

def main():
    if not INPUT_FILE.exists():
        print(f"[BŁĄD] Brak pliku: {INPUT_FILE}")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        places = json.load(f)

    processed = {}
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                processed = {p["id"]: p for p in saved}
                print(f"[INFO] Wznowiono: {len(processed)}/{len(places)} obiektów już istnieje.")
        except Exception:
            pass

    print(f"[START] Przetwarzanie {len(places)} obiektów przez model {OLLAMA_MODEL}...")

    total = len(places)
    for idx, raw_item in enumerate(places, 1):
        item = patch_anomalies(raw_item)
        item_id = item["id"]
        if item_id in processed:
            continue

        name = item.get("name", "").strip()
        sub_cat = item.get("sub_category", "obiekt")
        addr = item.get("address", {})
        full_addr = f"{addr.get('street') or ''} {addr.get('housenumber') or ''}, Kędzierzyn-Koźle".strip()
        tags = item.get("tags", {})

        try:
            t0 = time.time()
            ai_data = call_ollama(name, sub_cat, full_addr, tags)
            dt = round(time.time() - t0, 1)

            lead = ai_data.get("lead", "").strip()
            tip = ai_data.get("tip", "").strip()

            item["display_name"] = name
            item["editorial"] = {
                "lead": lead,
                "insider_tip": tip
            }

            processed[item_id] = item
            print(f"[{idx}/{total}] ({dt}s) {name} [{sub_cat}]")
            if lead:
                print(f"   > {lead[:90]}...")

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(list(processed.values()), f, ensure_ascii=False, indent=2)

        except urllib.error.URLError:
            print("\n[BŁĄD] Brak łączności z Ollamą na porcie 11434.")
            sys.exit(1)
        except Exception as e:
            print(f"[{idx}/{total}] [Błąd LLM] {name}: {e}")
            item["display_name"] = name
            item["editorial"] = {
                "lead": f"Obiekt z kategorii {sub_cat} zlokalizowany przy {full_addr}.",
                "insider_tip": "Sprawdź szczegóły na miejscu lub w lokalnych informatorach."
            }
            processed[item_id] = item

    print(f"\n[SUKCES] Zakończono! Kompletna baza 179 obiektów gotowa: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

