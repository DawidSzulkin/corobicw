import importlib
import inspect
from pathlib import Path
from typing import List, Type

from src.scrapers.base import BaseScraper

SCRAPERS_DIR = Path(__file__).resolve().parent


def _discover_scraper_classes(package_path: str, dir_path: Path) -> List[Type[BaseScraper]]:
    """Automatycznie importuje moduły z katalogu i zwraca zdefiniowane w nich klasy potomne BaseScraper."""
    classes = []
    if not dir_path.exists() or not dir_path.is_dir():
        return classes

    for py_file in sorted(dir_path.glob("*.py")):
        if py_file.name.startswith("__") or py_file.name.startswith("debug_"):
            continue

        module_name = f"{package_path}.{py_file.stem}"
        try:
            mod = importlib.import_module(module_name)
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, BaseScraper) and obj is not BaseScraper and obj.__module__ == module_name:
                    classes.append(obj)
        except Exception as e:
            print(f"[REGISTRY] Błąd importu modułu '{module_name}': {e}")

    return classes


def get_scrapers_for_city(city_tag: str, partner_id: str = "") -> List[BaseScraper]:
    normalized_tag = city_tag.strip().lower()
    scrapers: List[BaseScraper] = []

    # 1. Auto-discovery scraperów lokalnych: src/scrapers/<city_tag>/*.py
    city_dir = SCRAPERS_DIR / normalized_tag
    local_classes = _discover_scraper_classes(f"src.scrapers.{normalized_tag}", city_dir)
    for cls in local_classes:
        try:
            scrapers.append(cls())
        except Exception as e:
            print(f"[REGISTRY] Błąd inicjalizacji {cls.__name__}: {e}")

    # 2. Auto-discovery scraperów ogólnopolskich: src/scrapers/national/*.py
    national_dir = SCRAPERS_DIR / "national"
    national_classes = _discover_scraper_classes("src.scrapers.national", national_dir)
    for cls in national_classes:
        try:
            scrapers.append(cls(city_tag=normalized_tag, partner_id=partner_id))
        except TypeError:
            try:
                scrapers.append(cls(city_tag=normalized_tag))
            except TypeError:
                scrapers.append(cls())
        except Exception as e:
            print(f"[REGISTRY] Błąd inicjalizacji ogólnopolskiego {cls.__name__}: {e}")

    return scrapers