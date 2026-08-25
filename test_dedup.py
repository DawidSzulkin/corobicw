import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.dedup import deduplicate_events
from src.scrapers.kedzierzyn_kozle.kedzierzynkozle_pl import KedzierzynKozlePlScraper
from src.scrapers.kedzierzyn_kozle.mok_kkozle_pl import MokKkozlePlScraper

def run_dedup_test():
    print("=== POBIERANIE DANYCH DO DEDUPLIKACJI ===")
    
    mok = MokKkozlePlScraper().fetch_events()
    um = KedzierzynKozlePlScraper().fetch_events()

    total_before = len(mok) + len(um)
    print(f"\nPobrano z MOK: {len(mok)} | Pobrano z UM: {len(um)} | Suma: {total_before}")

    all_raw = mok + um
    deduped = deduplicate_events(all_raw)

    print(f"\n=== WYNIK DEDUPLIKACJI ===")
    print(f"Przed: {total_before} -> Po: {len(deduped)} (Usunięto/Scalono duplikatów: {total_before - len(deduped)})")

    print("\n--- Zscalona lista wydarzeń ---")
    for ev in sorted(deduped, key=lambda x: x["date"]):
        print(f"[{ev['date']}] {ev['time_start']} | {ev['venue']} | {ev['title'][:40]}")

if __name__ == "__main__":
    run_dedup_test()