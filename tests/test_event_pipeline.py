import pytest
from src.domain.pipeline import _prepare_full_event_pages
from src.core.models import FullEventPage

@pytest.fixture
def base_city_cfg():
    return {
        "city": "Bielsko-Biała",
        "city_tag": "bielsko_biala",
        "venue_match_rules": []
    }

@pytest.fixture
def minimal_event():
    return {
        "title": "Koncert Symfoniczny",
        "date_start": "2026-10-15",
        "time_start": "19:00",
        "price_range": "50-120 zł",
        "image_url": "https://example.com/img.jpg",
        "source_url": "https://example.com/event"
    }

# ==========================================
# 1. TESTY RESOLVED_PID (MAPOWANIE MIEJSC)
# ==========================================

def test_resolved_pid_from_place_dict_place_id(minimal_event, base_city_cfg):
    """Klucz 'place_id' w słowniku miejsca (format places_clean.json)."""
    minimal_event["place_id"] = "venue-slug-1"
    places = {
        "venue-slug-1": {
            "place_id": "venue-slug-1",
            "name": "Klub Muzyczny"
        }
    }
    pages = _prepare_full_event_pages([minimal_event], places, base_city_cfg, "Bielsko-Biała")
    assert len(pages) == 1
    assert pages[0].place_id == "venue-slug-1"
    assert pages[0].analysis.ticket_info.place_id == "venue-slug-1"

def test_resolved_pid_from_place_dict_id_or_slug(minimal_event, base_city_cfg):
    """Klucz 'id' lub 'slug' w słowniku miejsca ze scrapera zewnętrznego."""
    minimal_event["place_id"] = "venue-legacy"
    places = {
        "venue-legacy": {
            "id": "venue-legacy-id",
            "name": "Teatr Stary"
        }
    }
    pages = _prepare_full_event_pages([minimal_event], places, base_city_cfg, "Bielsko-Biała")
    assert len(pages) == 1
    assert pages[0].place_id == "venue-legacy-id"

def test_resolved_pid_fallback_when_place_not_in_index(minimal_event, base_city_cfg):
    """Fallback do e.place_id gdy miejsce nie istnieje w places_by_id."""
    minimal_event["place_id"] = "unindexed-venue"
    pages = _prepare_full_event_pages([minimal_event], {}, base_city_cfg, "Bielsko-Biała")
    assert len(pages) == 1
    assert pages[0].place_id == "unindexed-venue"

def test_resolved_pid_fallback_to_analysis_ticket_info(minimal_event, base_city_cfg):
    """Fallback do analysis.ticket_info.place_id gdy brak root place_id."""
    minimal_event["analysis"] = {
        "ticket_info": {"place_id": "deep-nested-slug", "venue_name": "Scena"}
    }
    pages = _prepare_full_event_pages([minimal_event], {}, base_city_cfg, "Bielsko-Biała")
    assert len(pages) == 1
    assert pages[0].place_id == "deep-nested-slug"

# ==========================================
# 2. TESTY FLAGI IS_CANCELLED
# ==========================================

@pytest.mark.parametrize("event_patch,expected_cancelled", [
    ({"price_range": "Występ odwołany"}, True),
    ({"price_range": "Odwołane przez organizatora"}, True),
    ({"price_range": "Cancelled event"}, True),
    ({"title": "Spektakl [ODWOŁANE]"}, True),
    ({"status": "cancelled"}, True),
    ({"ticket_offers": [{"provider": "Kasa", "url": "http://x", "price": "Odwołane"}]}, True),
    ({"price_range": "Bilety od 40 zł"}, False),
    ({"price_range": "Wstęp wolny"}, False),
    ({"price_range": ""}, False),
])
def test_is_cancelled_detection(minimal_event, base_city_cfg, event_patch, expected_cancelled):
    """Weryfikacja wyliczania flagi is_cancelled na poziomie potoku."""
    minimal_event.update(event_patch)
    pages = _prepare_full_event_pages([minimal_event], {}, base_city_cfg, "Bielsko-Biała")
    assert len(pages) == 1
    assert pages[0].is_cancelled is expected_cancelled