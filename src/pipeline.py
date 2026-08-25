from datetime import datetime
from src.db import get_active_events, save_event
from src.enricher import enrich_missing_descriptions
from src.models import FullEventPage
from src.normalizer import create_event_record
from src.renderer import HTMLRenderer
from src.scrapers.registry import get_scrapers_for_city


def run_city_pipeline(city_cfg: dict, renderer: HTMLRenderer, output_dir: str = "docs") -> int:
    city_tag = city_cfg.get("city_tag")
    city_name = city_cfg.get("city", city_tag)

    if not city_tag:
        raise ValueError("Brak zdefiniowanego 'city_tag' w przekazanej konfiguracji.")
    
    print(f"\n==========================================")
    print(f"  URUCHAMIANIE PIPELINE: {city_name.upper()} ({city_tag})")
    print(f"==========================================")

    # FAZA 1: Pobieranie ze scraperów
    scrapers = get_scrapers_for_city(city_tag)
    all_raw_events = []
    for scraper in scrapers:
        print(f"\n--- FAZA 1: SKANOWANIE {scraper.source_name} ---")
        try:
            items = scraper.fetch_events()
            all_raw_events.extend(items)
        except Exception as e:
            print(f"[{scraper.source_name}] BŁĄD SCRAPERA: {e}")

    print(f"\nŁącznie pobrano surowych rekordów dla {city_name}: {len(all_raw_events)}")

    # FAZA 2: Zapis i scalanie duplikatów
    print(f"\n--- FAZA 2: DEDUPLIKACJA I ZAPIS W BAZIE ({city_tag}) ---")
    stats = {"created": 0, "merged_duplicate": 0, "updated_url": 0}
    for ev in all_raw_events:
        page_obj = create_event_record(ev, default_city_name=city_name)
        status = save_event(city_tag, page_obj.model_dump())
        stats[status] = stats.get(status, 0) + 1

    print(f"Wyniki: Nowe: {stats.get('created', 0)} | Zscalone: {stats.get('merged_duplicate', 0)} | Odświeżone: {stats.get('updated_url', 0)}")

    # FAZA 3: LLM / OCR
    enrich_missing_descriptions(city_tag)

    # FAZA 4: Renderowanie podstron i widoku miasta
    print(f"\n--- FAZA 4: GENEROWANIE HTML DLA {city_name} ---")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    raw_active = get_active_events(city_tag, min_date=today_iso)

    valid_pages = []
    for item in raw_active:
        try:
            valid_pages.append(FullEventPage(**item))
        except Exception as e:
            print(f"  [Ostrzeżenie] Pomijam wadliwy rekord '{item.get('title')}': {e}")

    renderer.render_city(
        city_name=city_name,
        city_tag=city_tag,
        events=valid_pages,
        output_dir=output_dir
    )
    print(f"Wyrenderowano pomyślnie {len(valid_pages)} wydarzeń.")
    return len(valid_pages)