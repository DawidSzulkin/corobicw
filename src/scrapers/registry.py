from typing import List

# Scrapery ogólnopolskie
from src.scrapers.national.biletyna_pl import BiletynaPlScraper
from src.scrapers.national.kupbilecik_pl import KupBilecikPlScraper

# Scrapery dedykowane: Bielsko-Biała
from src.scrapers.bielsko_biala.banialuka_pl import BanialukaPlScraper
from src.scrapers.bielsko_biala.teatr_bielsko_pl import TeatrBielskoPlScraper

# Scrapery dedykowane: Kędzierzyn-Koźle
from src.scrapers.kedzierzyn_kozle.kedzierzynkozle_pl import KedzierzynKozlePlScraper
from src.scrapers.kedzierzyn_kozle.mbpkk_pl import MbpKkPlScraper
from src.scrapers.kedzierzyn_kozle.mok_kkozle_pl import MokKkozlePlScraper
from src.scrapers.kedzierzyn_kozle.mosirkk_pl import MosirKkPlScraper

# Rejestr parserów przypisanych do konkretnego miasta
LOCAL_SCRAPERS = {
    "kedzierzyn_kozle": [
        MokKkozlePlScraper,
        KedzierzynKozlePlScraper,
        MosirKkPlScraper,
        MbpKkPlScraper,
    ],
    "bielsko_biala": [
        TeatrBielskoPlScraper,
        BanialukaPlScraper,
    ],
}

# Parser-agregatory ogólnopolskie uruchamiane dla każdego aktywnego miasta
NATIONAL_SCRAPERS = [
    KupBilecikPlScraper,
    BiletynaPlScraper,
]


def get_scrapers_for_city(city_tag: str, partner_id: str = "") -> List:
    normalized_tag = city_tag.strip().lower()
    scrapers = []

    # 1. Instancjonowanie scraperów lokalnych
    local_classes = LOCAL_SCRAPERS.get(normalized_tag, [])
    for cls in local_classes:
        scrapers.append(cls())

    # 2. Instancjonowanie scraperów ogólnopolskich z parametrem miasta
    for cls in NATIONAL_SCRAPERS:
        scrapers.append(cls(city_tag=normalized_tag, partner_id=partner_id))

    return scrapers