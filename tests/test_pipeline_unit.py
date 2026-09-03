import pytest
import sqlite3
import json
from pathlib import Path
from src.domain.pipeline import _are_titles_duplicate, deduplicate_events
from src.infrastructure.db import sync_city_events

def test_dedup_exact_title():
    """Weryfikuje identyczne tytuły."""
    assert _are_titles_duplicate("Koncert Organowy", "Koncert Organowy") is True

def test_dedup_stopwords_and_variations():
    """Weryfikuje odrzucanie słów pospolitych i wariacji miast."""
    assert _are_titles_duplicate(
        "Stand-up: Nowy Program na żywo w Bielsku",
        "Nowy Program Standup Bielsko-Biała"
    ) is True

def test_dedup_distinct_hours():
    """Różnica >= 45 minut nie powinna być łączona w jeden rekord."""
    assert _are_titles_duplicate("Kordian", "Kordian", time1="17:00", time2="19:30") is False
    assert _are_titles_duplicate("Kordian", "Kordian", time1="17:00", time2="17:15") is True

def test_deduplicate_events_merges_data():
    """Sprawdza wybór najpełniejszego (najdłuższego) tytułu i scalanie miniatur/miejsc wg Record Merge."""
    events = [
        {
            "title": "Długi Tytuł Spektaklu Teatralnego",
            "date_start": "2026-10-10",
            "time_start": "19:00",
            "venue": "Teatr Polski",
            "image_url": "http://example.com/img1.jpg",
            "source_url": "http://source1.com"
        },
        {
            "title": "Spektakl Teatralny",
            "date_start": "2026-10-10",
            "time_start": "19:00",
            "venue": "",
            "image_url": "/assets/thumbnails/teatr.jpg",
            "source_url": "http://source2.com"
        }
    ]
    res = deduplicate_events(events, city_name="Bielsko-Biała")
    assert len(res) == 1
    assert res[0]["title"] == "Długi Tytuł Spektaklu Teatralnego"
    assert res[0]["image_url"] == "/assets/thumbnails/teatr.jpg"
    assert res[0]["venue"] == "Teatr Polski"

def test_sync_city_events_db_isolation(tmp_path, monkeypatch):
    """Weryfikuje atomowe czyszczenie i wstawianie rekordów w SQLite."""
    test_db = tmp_path / "test_events.db"
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_tag TEXT,
            source_url TEXT,
            date_start TEXT,
            title TEXT,
            payload TEXT
        )
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr("src.infrastructure.db.Path", lambda p: test_db if "events.db" in str(p) else Path(p))

    mock_events = [
        {"title": "Event 1", "date_start": "2026-10-15", "source_url": "http://a.pl"},
        {"title": "Event 2", "date_start": "2026-10-16", "source_url": "http://b.pl"}
    ]
    sync_city_events("opole", mock_events)

    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events WHERE city_tag = 'opole'")
    assert cursor.fetchone()[0] == 2
    conn.close()