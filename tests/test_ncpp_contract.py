from src.infrastructure.scrapers.opole.ncpp_opole_pl import NcppOpolePlScraper

def test_ncpp_contract():
    scraper = NcppOpolePlScraper()
    events = scraper.fetch_events()
    assert isinstance(events, list)
    assert len(events) > 0, "NCPP scraper powinien zwrócić przynajmniej jedno nadchodzące wydarzenie"

    for ev in events:
        assert ev["title"], "Brak tytułu"
        assert ev["date_start"], "Brak daty startowej"
        assert ev["venue"], "Brak miejsca"
        assert ev["city_tag"] == "opole"
        assert ev["source"] == "ncpp_opole_pl"