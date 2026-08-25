from typing import List, Type
from src.scrapers.kedzierzyn_kozle.kedzierzynkozle_pl import KedzierzynKozlePlScraper
from src.scrapers.kedzierzyn_kozle.mok_kkozle_pl import MokKkozlePlScraper
from src.scrapers.kedzierzyn_kozle.mosirkk_pl import MosirKkPlScraper

SCRAPER_REGISTRY = {
    "kedzierzyn_kozle": [
        MokKkozlePlScraper,
        KedzierzynKozlePlScraper,
        MosirKkPlScraper,
    ],
    # Dodanie kolejnego miasta wymaga wpisania tylko nowej pozycji tutaj:
    # "krakow": [KrakowPlScraper, KupBilecikKrakowScraper],
}


def get_scrapers_for_city(city_tag: str) -> List:
    scraper_classes = SCRAPER_REGISTRY.get(city_tag, [])
    return [cls() for cls in scraper_classes]