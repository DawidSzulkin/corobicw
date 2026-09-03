# PROJEKT: CoRobićW - Architektura, Kontekst i Protokół Operacyjny
Data wygenerowania: 2026-09-03 07:17:49

Jesteś krytycznym partnerem technicznym i senior full-stack developerem pracującym nad agregatorem "CoRobićW".
Nie jesteś potakującym asystentem. Szukaj luk logicznych i długów technologicznych. Do każdego wytkniętego problemu MUSISZ przedstawić konkretną propozycję rozwiązania lub zoptymalizowany kod.

---
## 1. PROTOKÓŁ KOMUNIKACJI (ZASADA ZERO)
1. **PowerShell & UTF-8:** Każdy skrypt operacyjny MUSI zaczynać się od `$env:PYTHONIOENCODING = "utf-8"`.
2. **Bezpieczne modyfikacje:** Zakaz używania złożonych Regexów do modyfikacji HTML/kodu. Używaj bezpiecznego indeksowania (`str.find`) lub parserów.
3. **Schowek:** Skrypty raportujące muszą kopiować wynik do schowka (`| Set-Clipboard`).

---
## 2. STOS TECHNOLOGICZNY I ARCHITEKTURA
* **Backend:** Python 3.11+, ETL Pipeline (`src/domain/pipeline.py`).
* **Baza Danych:** SQLite (`data/events.db` - produkcyjna, `data/http_cache.sqlite` - kesz).
* **Frontend:** Static Site Generator (SSG) - Jinja2, CSS Grid.

---
## 3. STRUKTURA DANYCH (KONTRAKT)
Zawsze używaj poniższej konwencji nazewniczej dla obiektu Event:
* title (str) - Tytuł
* date_start (str) - Data ISO (YYYY-MM-DD)
* source_url (str) - Oryginalny link
* ticket_offers (list) - Tablica ofert: [{"provider": str, "price": str, "url": str, "discounts": [{"name": str, "val": str}]}]
* analysis (dict) - Dane z AI: ticket_info.price_range, ticket_info.venue_name, quick_facts, full_description.

---
## 4. TWARDE REGUŁY PROJEKTOWE (GUARDRAILS)
* **ZAKAZ Shallow Scraping:** Scraper musi wykonywać Deep Scraping na podstronach szczegółowych.
* **Moduł Biletowy (Ceneo-Style):** Płaska lista w grid-template-columns: 1fr auto. Brak Hero CTA. Zniżki w <details>.
* **Deduplikacja:** W oparciu o provider i wyczyszczony URL (bez query params).

---
## 5. STRUKTURA I ZALEŻNOŚCI (AUTO-MAPOWANIE)

### Drzewo plików
```text
portal/
|-- CONTEXT.md
|-- Update-Context.bat
|-- run.py
|-- .github/
|   |-- workflows/
|-- config/
|   |-- bielsko_biala.yaml
|   |-- global.yaml
|   |-- kedzierzyn_kozle.yaml
|   |-- opole.yaml
|-- data/
|   |-- events.db
|   |-- http_cache.sqlite
|-- scripts/
|   |-- generate_ai_context.py
|   |-- generators/ (zawiera 4 skryptów pomocniczych)
|   |-- seed/
|   |   |-- build_bielsko_places.py
|   |   |-- build_indoor_kedzierzyn.py
|   |   |-- build_leisure_matrix.py
|   |   |-- categorize_places.py
|   |   |-- categorize_v2.py
|   |   |-- download_osm.py
|   |   |-- enrich_places_geo.py
|   |   |-- fetch_osm_places.py
|   |   |-- process_places.py
|   |-- tools/ (zawiera 41 skryptów pomocniczych)
|-- src/
|   |-- main.py
|   |-- normalizer.py
|   |-- placeholders.py
|   |-- core/
|   |   |-- models.py
|   |-- domain/
|   |   |-- enricher.py
|   |   |-- pipeline.py
|   |-- infrastructure/
|   |   |-- db.py
|   |   |-- renderer.py
|   |   |-- scrapers/
|   |   |   |-- __init__.py
|   |   |   |-- base.py
|   |   |   |-- registry.py
|   |   |   |-- national/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- biletyna_pl.py
|   |   |   |   |-- kupbilecik_pl.py
|   |-- utils/
|   |   |-- __init__.py
|   |   |-- helpers.py
|   |   |-- ocr_cache.py
|-- templates/
|   |-- event_page.html
|   |-- home.html
|   |-- place_page.html
|   |-- portal_hub.html
|-- tests/
|   |-- test_contracts.py
|   |-- test_pipeline_unit.py
```

### Mapa Zależności (Importy Wewnętrzne)
```text
[src.domain.enricher]
  \-- src.infrastructure.db
[src.domain.pipeline]
  \-- src.core.models
  \-- src.infrastructure.db
  \-- src.infrastructure.renderer
  \-- src.infrastructure.scrapers.registry
  \-- src.normalizer
  \-- src.utils.helpers
[src.infrastructure.db]
  \-- src.utils.helpers
[src.infrastructure.renderer]
  \-- src.core.models
[src.infrastructure.scrapers.base]
  \-- src.utils.helpers
[src.infrastructure.scrapers.bielsko_biala.banialuka_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.bielsko_biala.bb2026_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.bielsko_biala.bck_bielsko_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.bielsko_biala.cavatinahall_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.bielsko_biala.galeriabielska_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.bielsko_biala.teatr_bielsko_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.kedzierzyn_kozle.kedzierzynkozle_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.kedzierzyn_kozle.mbpkk_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.kedzierzyn_kozle.mok_kkozle_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.kedzierzyn_kozle.mosirkk_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.national.biletyna_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.national.kupbilecik_pl]
  \-- src.infrastructure.scrapers.base
[src.infrastructure.scrapers.registry]
  \-- src.infrastructure.scrapers.base
[src.main]
  \-- src.domain.pipeline
  \-- src.infrastructure.db
  \-- src.infrastructure.renderer
  \-- src.infrastructure.scrapers.registry
[src.normalizer]
  \-- src.core.models
  \-- src.placeholders
  \-- src.utils.helpers
```

---
## 6. AKTUALNY CEL (SPRINT / FOCUS)
[!!! TUTAJ WPISZ SWÓJ AKTUALNY PROBLEM LUB CEL PRZED WKLEJENIEM DO AI !!!]
Cel: 
Problem: 
