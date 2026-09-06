import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def run_cmd(cmd, desc):
    print(f"\n[KROK] {desc}...")
    # Wymuszenie PYTHONPATH i UTF-8 dla procesów potomnych
    env = dict(sys.modules['os'].environ)
    env["PYTHONPATH"] = str(BASE_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    
    result = subprocess.run(cmd, shell=True, env=env)
    if result.returncode != 0:
        print(f"[BŁĄD] {desc} zakończone niepowodzeniem (kod: {result.returncode}). Przerywam potok.")
        sys.exit(result.returncode)
    print(f"[OK] {desc} zakończone sukcesem.")

def main():
    parser = argparse.ArgumentParser(description="Automatyczny orkiestrator potoku CoRobićW")
    parser.add_argument("--city", type=str, default=None, help="Tag miasta (np. bielsko_biala, opole, kedzierzyn_kozle). Brak = wszystkie miasta.")
    parser.add_argument("--all", action="store_true", help="Wykonaj potok dla wszystkich zarejestrowanych miast")
    parser.add_argument("--skip-tests", action="store_true", help="Pomiń testy kontraktowe pytest")
    parser.add_argument("--preflight", action="store_true", help="Uruchom preflight healthcheck przed scrapingiem")
    parser.add_argument("--render-only", action="store_true", help="Kompiluj tylko szablony HTML z bazy SQLite bez scrapowania")
    parser.add_argument("--docker", action="store_true", help="Uruchom w kontenerze Docker")
    args = parser.parse_args()

    # Tryb 1: Kompilacja wyłącznie z SQLite
    if args.render_only:
        city_flag = f"--city {args.city}" if (args.city and not args.all) else ""
        run_cmd(f'"{sys.executable}" -u src/main.py --render-only {city_flag}'.strip(), "Renderowanie SSG z SQLite")
        return

    # Krok 1: Testy kontraktowe DOM
    if not args.skip_tests and not args.docker:
        test_file = BASE_DIR / "tests" / "test_contracts.py"
        if test_file.exists():
            run_cmd(f'"{sys.executable}" -m pytest "{test_file}" -q', "Testy kontraktowe selektorów DOM")
        else:
            print("[INFO] Pomijam testy kontraktowe (brak pliku test_contracts.py).")

    # Krok 2: Opcjonalny preflight selektorów
    target_city = None if args.all else args.city
    city_param = f"--city {target_city}" if target_city else ""

    if args.preflight and not args.docker:
        run_cmd(f'"{sys.executable}" -u src/main.py --preflight {city_param}'.strip(), "Healthcheck selektorów źródeł")

    # Krok 3: Główny potok (Scraping + Normalizacja + Baza + Renderowanie)
    if args.docker:
        run_cmd("docker-compose up --build", "Budowa i uruchomienie w Dockerze")
    else:
        desc_target = f"dla miasta {target_city}" if target_city else "dla WSZYSTKICH miast"
        run_cmd(f'"{sys.executable}" -u src/main.py {city_param}'.strip(), f"Główny potok agregacji {desc_target}")

if __name__ == '__main__':
    main()
