import argparse
import importlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

def validate_date(date_str: str) -> bool:
    if not date_str:
        return False
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str))

def run_scraper_test(city_tag: str, scraper_module: str):
    print(f"\n=======================================================")
    print(f" TEST LOKALNY SCRAPERA: {city_tag}/{scraper_module}")
    print(f"=======================================================")

    module_path = f"src.scrapers.{city_tag}.{scraper_module}"
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        print(f"[BLAD] Nie znaleziono modulu '{module_path}': {e}")
        return

    # Znalezienie klasy scrapera w module
    scraper_cls = None
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and attr.endswith("Scraper") and attr != "BaseScraper":
            scraper_cls = obj
            break

    if not scraper_cls:
        print(f"[BLAD] Nie znaleziono klasy dziedziczacej po BaseScraper w {module_path}")
        return

    print(f"[INFO] Inicjalizacja klasy: {scraper_cls.__name__}")
    scraper = scraper_cls()

    start_t = datetime.now()
    try:
        events = scraper.fetch_events()
    except Exception as e:
        print(f"[KRYTYCZNY BLAD] Scraper wyrzucil wyjatek podczas fetch_events(): {e}")
        import traceback
        traceback.print_exc()
        return

    duration = (datetime.now() - start_t).total_seconds()
    print(f"[OK] Pobieranie zakonczone w {duration:.2f}s. Znaleziono: {len(events)} pozycji.\n")

    if not events:
        print("[OSTRZEZENIE] Scraper zwrocil pusta liste wydarzen!")
        return

    # Walidacja jakosciowa
    missing_images = 0
    invalid_dates = 0
    missing_sources = 0
    free_events = 0
    past_events = 0
    today_iso = datetime.now().strftime("%Y-%m-%d")

    for ev in events:
        if not ev.get("image_url"):
            missing_images += 1
        if not validate_date(ev.get("date_start")):
            invalid_dates += 1
        elif ev.get("date_start") < today_iso:
            past_events += 1
        if not ev.get("source_url"):
            missing_sources += 1
        if "bezpłat" in str(ev.get("price_range", "")).lower():
            free_events += 1

    print("--- RAPORT WALIDACJI DANYCH ---")
    print(f"* Wszystkie pobrane:       {len(events)}")
    print(f"* Prawidlowy format daty:  {len(events) - invalid_dates}/{len(events)}")
    print(f"* Wydarzenia przyszle:     {len(events) - past_events}/{len(events)}")
    print(f"* Posiada miniatury/plakat:{len(events) - missing_images}/{len(events)}")
    print(f"* Wstep bezplatny:         {free_events}/{len(events)}")
    print(f"* Posiada zrodlowy URL:    {len(events) - missing_sources}/{len(events)}")

    print("\n--- PODGLAD PIERWSZYCH 2 POZYCJI ---")
    for i, ev in enumerate(events[:2]):
        print(f"\n[{i+1}] {ev.get('title')}")
        print(f"    Termin:      {ev.get('date_start')} | Start: {ev.get('time_start')}")
        print(f"    Miejsce:     {ev.get('venue')} ({ev.get('address')})")
        print(f"    Cena:        {ev.get('price_range')}")
        print(f"    Grafika:     {ev.get('image_url')}")
        print(f"    URL zrodla:  {ev.get('source_url')}")
        lead = (ev.get('description') or '')[:120]
        print(f"    Opis:        {lead}...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lokalny tester scraperow")
    parser.add_argument("city", nargs="?", default="bielsko_biala", help="Tag miasta (np. bielsko_biala)")
    parser.add_argument("scraper", nargs="?", default="bb2026_pl", help="Nazwa pliku scrapera bez .py (np. bb2026_pl)")
    args = parser.parse_args()

    run_scraper_test(args.city, args.scraper)
