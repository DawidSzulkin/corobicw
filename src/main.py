import argparse
from pathlib import Path
import sys
import yaml

# Ścieżka bazowa do głównego katalogu projektu
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.db import init_db
from src.pipeline import run_city_pipeline
from src.renderer import HTMLRenderer


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}


def main():
    parser = argparse.ArgumentParser(description="Generator portalu wydarzeń miejskich")
    parser.add_argument("--city", type=str, help="Uruchom tylko dla wybranego city_tag (np. kedzierzyn_kozle)")
    args = parser.parse_args()

    init_db()
    renderer = HTMLRenderer()
    
    output_dir = BASE_DIR / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)

    config_dir = BASE_DIR / "config"
    if not config_dir.exists():
        print(f"[BŁĄD] Katalog konfiguracji nie istnieje: {config_dir}")
        return

    config_files = sorted(list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml")))
    active_cities = []

    for cfg_path in config_files:
        city_cfg = load_yaml(cfg_path)
        city_tag = city_cfg.get("city_tag")
        city_name = city_cfg.get("city")

        if not city_tag or not city_name:
            print(f"[POMINIĘTO] Plik {cfg_path.name} nie zawiera wymaganych pól 'city_tag' oraz 'city'.")
            continue

        if args.city and args.city.lower() != city_tag.lower():
            continue

        print(f"\n{'='*20} PRZETWARZANIE: {city_name.upper()} ({city_tag}) {'='*20}")
        try:
            run_city_pipeline(city_cfg, renderer=renderer, output_dir=str(output_dir))
            active_cities.append({"name": city_name, "tag": city_tag})
        except Exception as e:
            print(f"[BŁĄD MIASTA] Nie udało się przetworzyć '{city_name}': {e}")

    # Renderowanie strony głównej (HUB) tylko przy pełnym przebiegu
    if not args.city and active_cities:
        print("\n=== GENEROWANIE STRONY GŁÓWNEJ (HUB) ===")
        renderer.render_portal_hub(active_cities=active_cities, output_dir=str(output_dir))

    print("\n[SUKCES] Synchronizacja zakończona.")


if __name__ == "__main__":
    main()