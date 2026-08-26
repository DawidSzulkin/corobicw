import os
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.db import get_active_events, save_event
from src.dedup import deduplicate_events
from src.enricher import enrich_missing_descriptions
from src.models import FullEventPage
from src.renderer import HTMLRenderer
from src.scrapers.registry import get_scrapers_for_city


def slugify(text: str) -> str:
    """Konwertuje tekst do bezpiecznego formatu URL (ASCII, lowercase, myślniki)."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Zamiana znaków specyficznych dla języka polskiego nieobsługiwanych przez NFKD
    pl_map = {"ł": "l", "Ł": "l"}
    for pl_char, ascii_char in pl_map.items():
        text = text.replace(pl_char, ascii_char)
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)


def _prepare_event_models(events: List[Any]) -> List[Any]:
    models = []
    for e in events:
        if isinstance(e, dict):
            if "analysis" not in e or not isinstance(e.get("analysis"), dict):
                desc = e.get("description") or e.get("title", "")
                lead = (desc[:197] + "...") if len(desc) > 200 else (desc or e.get("title", ""))
                e["analysis"] = {
                    "category": "Wydarzenie",
                    "badges": ["Wydarzenie"],
                    "organizer": e.get("venue") or "Organizator",
                    "editorial_lead": lead,
                    "full_description": desc,
                    "details_bullets": [e.get("title", "")],
                    "quick_facts": {
                        "duration": "~2h",
                        "age_rating": "Wszyscy",
                        "parking": "Dostępny w pobliżu obiektu"
                    },
                    "ticket_info": {
                        "time_start": e.get("time_start") or "Według harmonogramu",
                        "venue_name": e.get("venue") or "Wydarzenie",
                        "price_range": e.get("price_range") or "Sprawdź bilety / Wstęp wolny"
                    },
                    "address": e.get("address") or e.get("venue") or ""
                }

            date_start = str(e.get("date_start", "")).strip()[:10]
            existing_slug = e.get("slug", "")

            if not existing_slug:
                title_slug = slugify(e.get("title", ""))[:60].strip("-")
                e["slug"] = f"{date_start}-{title_slug}" if date_start else (title_slug or "wydarzenie")
            else:
                e["slug"] = slugify(existing_slug)

            if "date_end" not in e or not e.get("date_end"):
                e["date_end"] = e.get("date_start", "")
            if "date_formatted" not in e or not e.get("date_formatted"):
                e["date_formatted"] = e.get("date_start", "")
            if "image_url" not in e or not e.get("image_url"):
                e["image_url"] = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80"
            if "source_url" not in e:
                e["source_url"] = ""

            try:
                models.append(FullEventPage(**e))
            except Exception as err:
                print(f"[PIPELINE] Błąd walidacji rekordu {e.get('title')}: {err}")
                models.append(e)
        else:
            models.append(e)
    return models


def run_city_pipeline(
    city_cfg: Dict[str, Any],
    renderer: HTMLRenderer,
    output_dir: str,
    render_only: bool = False,
    source_filter: Optional[str] = None,
    skip_enrich: bool = False
) -> None:
    city_tag = city_cfg.get("city_tag", "").strip().lower()
    city_name = city_cfg.get("city", "").strip()
    partner_id = city_cfg.get("partner_id", "")
    today_iso = datetime.now().strftime("%Y-%m-%d")

    if not city_tag:
        print("[PIPELINE] Błąd: brak 'city_tag' w konfiguracji.")
        return

    print(f"\n==========================================")
    print(f"  URUCHAMIANIE PIPELINE: {city_name.upper()} ({city_tag})")
    print(f"==========================================")

    # --- TRYB: TYLKO RENDEROWANIE ---
    if render_only:
        print("\n--- FAZA 4: SZYBKIE GENEROWANIE HTML (render-only z bazy) ---")
        raw_events = get_active_events(city_tag=city_tag, min_date=today_iso)
        if not raw_events:
            print(f"[RENDERER] Brak aktywnych wydarzeń w bazie dla '{city_tag}'. Uruchom najpierw pełny scraping.")
            return
        event_models = _prepare_event_models(raw_events)
        renderer.render_city(
            city_name=city_name,
            city_tag=city_tag,
            events=event_models,
            output_dir=output_dir
        )
        return

    # --- FAZA 1: SKANOWANIE I SCRAPING ---
    scrapers = get_scrapers_for_city(city_tag, partner_id=partner_id)
    if source_filter:
        scrapers = [s for s in scrapers if s.source_name.lower() == source_filter.lower()]
        print(f"[PIPELINE] Filtr źródła: uruchamianie wyłącznie '{source_filter}' ({len(scrapers)} scraperów).")

    raw_events: List[Dict[str, Any]] = []
    for scraper in scrapers:
        print(f"\n--- FAZA 1: SKANOWANIE {scraper.source_name} ---")
        try:
            items = scraper.fetch_events()
            for it in items:
                it["city_tag"] = city_tag
            raw_events.extend(items)
            print(f"[{scraper.source_name}] Pomyślnie pobrano {len(items)} pozycji.")
        except Exception as e:
            print(f"[{scraper.source_name}] Błąd scrapera: {e}")

    print(f"\nŁącznie pobrano surowych rekordów dla {city_name}: {len(raw_events)}")

    # --- FAZA 2: DEDUPLIKACJA I ZAPIS W BAZIE ---
    print(f"\n--- FAZA 2: DEDUPLIKACJA I ZAPIS W BAZIE ({city_tag}) ---")
    deduped = deduplicate_events(raw_events)

    saved_count = 0
    for ev in deduped:
        try:
            save_event(city_tag=city_tag, event_data=ev)
            saved_count += 1
        except Exception as e:
            print(f"[DB] Błąd zapisu rekordu '{ev.get('title', '')}': {e}")

    print(f"Pomyślnie zapisano/zaktualizowano w bazie: {saved_count} unikalnych wydarzeń.")

    # --- FAZA 3: WZBOGACANIE TREŚCI (LLM / OCR) ---
    if skip_enrich:
        print(f"\n=== FAZA 3: POMINIĘTO WZBOGACANIE TREŚCI (--skip-enrich) ===")
    else:
        print(f"\n=== FAZA 3: WZBOGACANIE TREŚCI (OCR + LLM) ({city_tag}) ===")
        enrich_missing_descriptions(city_tag=city_tag)

    # --- FAZA 4: GENEROWANIE HTML ---
    print(f"\n--- FAZA 4: GENEROWANIE HTML DLA {city_name} ---")
    raw_events = get_active_events(city_tag=city_tag, min_date=today_iso)
    event_models = _prepare_event_models(raw_events)
    renderer.render_city(
        city_name=city_name,
        city_tag=city_tag,
        events=event_models,
        output_dir=output_dir
    )
