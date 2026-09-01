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
    args = parser.parse_args()

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

if __name__ == "__main__":
    main()
