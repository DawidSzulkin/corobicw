import sys
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.db import init_db
from src.scrapers.kedzierzyn_kozle.mok_kkozle_pl import MokKkozlePlScraper

def test_scraper():
    init_db()
    print("=== TEST JEDNOSTKOWY SCRAPERA MOK-KKOZLE.PL ===")
    
    scraper = MokKkozlePlScraper()
    events = scraper.fetch_events()

    print(f"\n[PODSUMOWANIE] Pobrano pomyślnie {len(events)} nowych rekordów.")
    
    if events:
        print("\n--- PRZYKŁADOWY POBRANY REKORD (1 z listy) ---")
        first = events[0]
        print(f"Tytuł:        {first['title']}")
        print(f"Data:         {first['date']}")
        print(f"Godzina:      {first['time_start']}")
        print(f"Miejsce:      {first['venue']}")
        print(f"Bilety:       {first['price_range']}")
        print(f"Plakat:       {first['image_url']}")
        print(f"URL Źródła:   {first['url']}")
        print(f"Długość opisu:{len(first['description'])} znaków")
        print("Początek opisu:")
        print(first['description'][:300] + "..." if len(first['description']) > 300 else first['description'])

if __name__ == "__main__":
    test_scraper()