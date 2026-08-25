from typing import List
from src.scrapers.kedzierzyn_kozle.kedzierzynkozle_pl import KedzierzynKozlePlScraper
from src.scrapers.kedzierzyn_kozle.mbpkk_pl import MbpKkPlScraper
from src.scrapers.kedzierzyn_kozle.mok_kkozle_pl import MokKkozlePlScraper
from src.scrapers.kedzierzyn_kozle.mosirkk_pl import MosirKkPlScraper

SCRAPER_REGISTRY = {
    "kedzierzyn_kozle": [
        MokKkozlePlScraper,
        KedzierzynKozlePlScraper,
        MosirKkPlScraper,
        MbpKkPlScraper,
    ],
}


def get_scrapers_for_city(city_tag: str) -> List:
    scraper_classes = SCRAPER_REGISTRY.get(city_tag, [])
    return [cls() for cls in scraper_classes]