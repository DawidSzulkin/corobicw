import pytest
from src.utils.helpers import resolve_ticket_provider
from src.domain.pipeline import _deduplicate_ticket_offers_list

def test_resolve_ticket_provider_authorities():
    # Instytucje miejskie i teatry -> priorytet 100, is_official=True
    prio, name, is_off = resolve_ticket_provider("https://bilety.ncpp.opole.pl/rezerwacja/numerowane.html?id=1")
    assert prio == 100
    assert name == "NCPP Opole"
    assert is_off is True

    prio, name, is_off = resolve_ticket_provider("https://cavatinahall.pl/wydarzenia/koncert")
    assert prio == 100
    assert name == "Cavatina Hall"
    assert is_off is True

    # Agregatory komercyjne -> priorytet 80, is_official=False
    prio, name, is_off = resolve_ticket_provider("https://biletyna.pl/koncert/Maryla-Rodowicz")
    assert prio == 80
    assert name == "Biletyna"
    assert is_off is False

    prio, name, is_off = resolve_ticket_provider("https://www.kupbilecik.pl/imprezy/123/Opole/")
    assert prio == 80
    assert name == "KupBilecik"
    assert is_off is False

def test_dual_tagging_official_and_best_price():
    """Gdy oficjalna kasa ma najniższą cenę, musi dostać OBA wyróżniki."""
    raw_offers = [
        {"url": "https://biletyna.pl/event/1", "price": "160 zł", "provider": "Biletyna"},
        {"url": "https://bilety.ncpp.opole.pl/event/1", "price": "140 zł", "provider": "NCPP Opole"},
        {"url": "https://kupbilecik.pl/event/1", "price": "180 zł", "provider": "KupBilecik"},
    ]
    
    deduped = _deduplicate_ticket_offers_list(raw_offers)
    
    assert len(deduped) == 3
    # NCPP powinno być pierwsze z powodu najniższej ceny
    ncpp = deduped[0]
    assert ncpp["provider"] == "NCPP Opole"
    assert ncpp["price"] == "140 zł"
    assert ncpp["is_official"] is True
    assert ncpp["official_badge"] == "Oficjalna kasa"
    assert ncpp["tag"] == "Najlepsza cena"
    assert ncpp["tag_class"] == "best-price"

def test_official_box_office_when_more_expensive():
    """Gdy agregator ma promocję, agregator dostaje 'Najlepsza cena', a instytucja nadal ma odznakę 'Oficjalna kasa'."""
    raw_offers = [
        {"url": "https://biletyna.pl/event/1", "price": "120 zł", "provider": "Biletyna"},
        {"url": "https://bilety.ncpp.opole.pl/event/1", "price": "140 zł", "provider": "NCPP Opole"},
    ]
    
    deduped = _deduplicate_ticket_offers_list(raw_offers)
    
    biletyna = next(o for o in deduped if "biletyna" in o["url"])
    ncpp = next(o for o in deduped if "ncpp" in o["url"])
    
    assert biletyna["tag"] == "Najlepsza cena"
    assert biletyna["is_official"] is False
    
    assert ncpp["is_official"] is True
    assert ncpp["official_badge"] == "Oficjalna kasa"