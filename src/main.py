import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
os.environ["PYTHONUTF8"] = "1"
import argparse
from pathlib import Path
import sys
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.infrastructure.db import init_db
from src.domain.pipeline import run_city_pipeline
from src.infrastructure.renderer import HTMLRenderer


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}


def main():
    parser = argparse.ArgumentParser(description="Generator portalu wydarzeń miejskich")
    parser.add_argument("--city", type=str, help="Uruchom tylko dla wybranego city_tag (np. bielsko_biala, kedzierzyn_kozle)")
    parser.add_argument("--render-only", action="store_true", help="Pomiń scraping i LLM – generuj HTML bezpośrednio z bazy danych")
    parser.add_argument("--source", type=str, help="Uruchom tylko wybrany scraper (np. cavatinahall_pl, banialuka_pl)")
    parser.add_argument("--skip-enrich", action="store_true", help="Pomiń fazę wzbogacania LLM/OCR")
    args = parser.parse_args()

    init_db()
    renderer = HTMLRenderer()
    
    # Zmiana z "docs" na "public", aby wszystko lądowało w jednym spójnym folderze
    output_dir = BASE_DIR / "public"
    output_dir.mkdir(parents=True, exist_ok=True)

    config_dir = BASE_DIR / "config"
    if not config_dir.exists():
        print(f"[BŁĄD] Katalog konfiguracji nie istnieje: {config_dir}")
        return

    config_files = sorted(list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml")))
    
    # 1. Pobierz wszystkie poprawnie zdefiniowane miasta do HUB-a
    all_configured_cities = []
    for cfg_path in config_files:
        city_cfg = load_yaml(cfg_path)
        city_tag = city_cfg.get("city_tag")
        city_name = city_cfg.get("city")

        if not city_tag or not city_name:
            if cfg_path.stem not in ["global", "schema"]:
                print(f"[POMINIĘTO] Plik {cfg_path.name} nie zawiera wymaganych pól 'city_tag' oraz 'city'.")
            continue

        all_configured_cities.append({
            "name": city_name,
            "tag": city_tag,
            "cfg": city_cfg
        })

    # 2. Przetwarzanie miast (z opcją filtrowania)
    for item in all_configured_cities:
        city_tag = item["tag"]
        city_name = item["name"]
        city_cfg = item["cfg"]

        if args.city and args.city.lower() != city_tag.lower():
            continue

        print(f"\n{'='*20} PRZETWARZANIE: {city_name.upper()} ({city_tag}) {'='*20}")
        try:
            run_city_pipeline(
                city_cfg,
                renderer=renderer,
                output_dir=str(output_dir),
                render_only=args.render_only,
                source_filter=args.source,
                skip_enrich=args.skip_enrich
            )
        except Exception as e:
            print(f"[BŁĄD MIASTA] Nie udało się przetworzyć '{city_name}': {e}")

    # 3. HUB zawsze uwzględnia wszystkie skonfigurowane miasta
    if not args.source and all_configured_cities:
        print("\n=== GENEROWANIE STRONY GŁÓWNEJ (HUB) ===")
        hub_cities = [{"name": c["name"], "tag": c["tag"]} for c in all_configured_cities]
        renderer.render_portal_hub(active_cities=hub_cities, output_dir=str(output_dir))
        
        # Wpięcie automatycznego generowania mapy witryny i SEO (przeniesione z usuniętego build_all.py)
        renderer.render_seo_files(output_dir=str(output_dir), base_url="https://corobicw.pl")

    print("\n[SUKCES] Synchronizacja zakończona.")


if __name__ == "__main__":
    main()
