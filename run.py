import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def run_cmd(cmd, desc):
    print(f"\n[KROK] {desc}...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[BŁĄD] {desc} zakończone niepowodzeniem (kod: {result.returncode}). Przerywam potok.")
        sys.exit(result.returncode)
    print(f"[OK] {desc} zakończone sukcesem.")

def main():
    parser = argparse.ArgumentParser(description="Automatyczny orkiestrator potoku agregacji wydarzeń")
    parser.add_argument("--city", type=str, default="bielsko_biala", help="Tag miasta")
    parser.add_argument("--skip-tests", action="store_true", help="Pomiń testy kontraktowe")
    parser.add_argument("--docker", action="store_true", help="Uruchom potok w kontenerze Docker")
    parser.add_argument("--skip-enrich", action="store_true", help="Pomiń fazę LLM/OCR")
    parser.add_argument("--render-only", action="store_true", help="Kompiluj tylko szablony HTML z bazy SQLite bez scrapowania")
    parser.add_argument("--all", action="store_true", help="Wykonaj dla wszystkich zarejestrowanych miast")
    args = parser.parse_args()
    if args.render_only:
        run_render_only(city_tag=args.city, all_cities=args.all)
        return

    # Krok 1: Testy kontraktowe wywoływane przez ten sam interpreter
    if not args.skip_tests and not args.docker:
        test_file = BASE_DIR / "tests" / "test_contracts.py"
        if test_file.exists():
            py_exe = sys.executable
            run_cmd(f'"{py_exe}" -m pytest "{test_file}" -q', "Testy kontraktowe selektorów DOM")
        else:
            print("[INFO] Brak pliku testów kontraktowych. Pomijam.")

    # Krok 2: Wykonanie potoku
    if args.docker:
        run_cmd("docker-compose up --build", "Budowa i uruchomienie w kontenerze Docker")
    else:
        enrich_flag = " --skip-enrich" if args.skip_enrich else ""
        py_exe = sys.executable
        run_cmd(f'"{py_exe}" -u src/main.py --city {args.city} --preflight{enrich_flag}', f"Główny potok dla miasta {args.city}")


def run_render_only(city_tag: str, all_cities: bool = False):
    import time
    import sqlite3
    import json
    from src.infrastructure.renderer import HTMLRenderer
    from src.core.models import FullEventPage
    from src.infrastructure.db import DB_PATH

    start_time = time.time()
    renderer = HTMLRenderer()
    
    cities_map = {
        "bielsko_biala": "Bielsko-Biała",
        "opole": "Opole",
        "kedzierzyn_kozle": "Kędzierzyn-Koźle"
    }
    
    target_tags = list(cities_map.keys()) if all_cities else [city_tag]
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    total = 0
    for tag in target_tags:
        c_name = cities_map.get(tag, tag)
        places = {}
        places_path = Path("data") / tag / "places_clean.json"
        if places_path.exists():
            try:
                p_data = json.loads(places_path.read_text(encoding="utf-8"))
                places = p_data if isinstance(p_data, dict) else {p.get("id"): p for p in p_data if "id" in p}
            except Exception:
                pass
                
        cur.execute("SELECT payload FROM events WHERE city_tag = ?", (tag,))
        events_models = [FullEventPage(**json.loads(r[0])) for r in cur.fetchall() if r[0]]
        total += len(events_models)
        
        renderer.render_city(
            city_name=c_name,
            city_tag=tag,
            events=events_models,
            places=places,
            output_dir="public"
        )
        print(f" -> Wyrenderowano {c_name} ({tag}): {len(events_models)} wydarzeń.")
        
    conn.close()
    renderer.render_seo_files(output_dir="public")
    print(f"\n[BUILD SSG] Zakończono renderowanie {len(target_tags)} miast w {time.time() - start_time:.2f}s (Łącznie: {total} wydarzeń).")


if __name__ == '__main__':
    main()
