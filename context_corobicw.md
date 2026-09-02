# PROJEKT: CoRobićW - Architektura, Kontekst i Protokół Operacyjny

Jesteś asystentem AI pracującym nad kodem dla lokalnego agregatora wydarzeń "CoRobićW". Traktuj ten dokument jako absolutne źródło prawdy o strukturze, logice projektu i zasadach współpracy.

---

## 1. PROTOKÓŁ KOMUNIKACJI (ZASADA ZERO)

Głównym kanałem naszej współpracy jest konsola **PowerShell** na środowisku Windows. Masz działać według ścisłej pętli:
1. **Wymuszenie kodowania sesji:** Każdy skrypt diagnostyczny i operacyjny w PowerShellu MUSI zaczynać się od jawnego ustawienia `$env:PYTHONIOENCODING = "utf-8"`, aby zapobiec zniekształceniom znaków przez powłokę (CP852/CP1250).
2. **Diagnoza przed akcją:** Zanim zaproponujesz modyfikację kodu, zawsze wygeneruj skrypt diagnostyczny sprawdzający faktyczny stan plików na dysku.
3. **Automatyzacja schowka:** Każdy skrypt diagnostyczny i raportujący musi automatycznie kopiować wynik do schowka (`| Set-Clipboard`).
4. **Brak założeń i bezpieczny zapis:** Nie zgaduj struktury ani zawartości klas. Wszystkie modyfikacje wieloliniowych plików Pythona mają być dokonywane za pomocą skryptów tworzących czyste pliki UTF-8 (np. `[System.IO.File]::WriteAllText`), aby wyeliminować błędy uciekania cudzysłowów i urwanych ciągów (`unterminated string literal`).
5. **Kompilacja sprawdzająca:** Każda modyfikacja kodu Pythona musi zakończyć się weryfikacją składni przez `py_compile`.

---

## 2. STOS TECHNOLOGICZNY I ARCHITEKTURA

* **Wzorzec:** Static Site Generator (SSG) zasilany zautomatyzowanym potokiem ETL (Extract, Transform, Load) z zabezpieczeniami Circuit Breaker i Contract Testing.
* **Język:** Python 3.11+.
* **Środowisko:** Lokalne oraz wyizolowany kontener Docker (`python:3.11-slim` z wymuszonym `LANG=C.UTF-8` i `PYTHONIOENCODING=utf-8`).
* **Baza danych:** Lokalne środowisko SQLite (`data/events.db` – główna baza wydarzeń, `data/http_cache.sqlite` – kesz żądań `requests-cache`).
* **Renderowanie:** Jinja2 (silnik generujący statyczny HTML w `public/`).
* **Testowanie i Audyt:** Pytest (testy kontraktowe selektorów DOM w `tests/`) + dedykowane skrypty audytu jakości danych (badające kompletność opisów, poprawność powiązań OSM i brak mojibake).
* **Wzbogacanie danych (AI/OCR):** RapidOCR do odczytu tekstów z plakatów + lokalny model LLM (Ollama) do strukturyzacji opisów i wydobywania brakujących informacji organizacyjnych.

---

## 3. MAPA KATALOGÓW (ZORIENTOWANIE W PRZESTRZENI)

```text
C:\Users\SZULKIN-KOMPUTER\Desktop\portal\
|-- Dockerfile               # Definicja wyizolowanego środowiska produkcyjnego (UTF-8, zależności systemowe)
|-- docker-compose.yml       # Orkiestracja kontenera z montowaniem wolumenów (data, config, public)
|-- run.py                   # GŁÓWNY ORKIESTRATOR ZADAŃ: Odpala testy kontraktowe -> preflight -> ETL -> build
|-- config/                  # Konfiguracje miast w YAML (opole.yaml, bielsko_biala.yaml, kedzierzyn_kozle.yaml)
|-- data/                    # Bazy SQLite oraz pliki przejściowe JSON
|   |-- [miasto]/            # Bazy miejsc i parkingów (places_raw.json, places_clean.json, parkings.json)
|   |-- processed/           # Oczyszczone i przetworzone zrzuty ze scraperów
|   |-- raw/                 # Surowe zrzuty scrapowanych danych z danego dnia
|   |-- events.db            # Główna relacyjna baza aktywnych wydarzeń
|   \-- http_cache.sqlite    # Kesz zapytań sieciowych modułu requests-cache
|-- scripts/                 # Narzędzia developerskie, diagnostyka, jednorazowe fixy bazy
|-- src/                     # GŁÓWNY KOD BACKENDU (PYTHON)
|   |-- core/                # models.py: Modele domenowe Pydantic (FullEventPage, EventAnalysis, QuickFacts)
|   |-- domain/              #
|   |   |-- pipeline.py      # SILNIK ETL: Pobiera, deduplikuje, dopasowuje OSM (place_id), czyści mojibake
|   |   \-- enricher.py      # Moduł wywołujący OCR i LLM (Ollama)
|   |-- infrastructure/      #
|   |   |-- db.py            # Warstwa SQLite (operacje CRUD, init bazy)
|   |   |-- renderer.py      # Klasa HTMLRenderer. Most między bazą a szablonami Jinja
|   |   \-- scrapers/        # Skrypty agregujące per miasto/kraj (Dziedziczą po base.py)
|   |       |-- base.py      # Klasa bazowa z obsługą CachedSession i miniatur WebP
|   |       |-- bielsko_biala/ # Dedykowane scrapery lokalne (bck, cavatina, banialuka, galeriabielska, teatr)
|   |       \-- national/    # Scrapery ogólnopolskie sparametryzowane miastem (kupbilecik, biletyna)
|   |-- main.py              # ENTRYPOINT ETL: CLI, rejestracja scraperów, Circuit Breaker, opcja --preflight
|   |-- normalizer.py        # Logika normalizacji stringów, dat (format polski) i adresów
|   \-- placeholders.py      # Definiowanie awaryjnych stanów danych
|-- tests/                   # TESTY INTEGRACYJNE I KONTRAKTOWE
|   \-- test_contracts.py    # Healthcheck selektorów DOM i endpointów zewnętrznych (Pytest)
|-- templates/               # GŁÓWNE SZABLONY FRONTENDOWE (JINJA2)
|   |-- event_page.html      # Szablon strony pojedynczego wydarzenia
|   |-- place_page.html      # Szablon strony obiektu/miejsca
|   |-- portal_hub.html      # Landing page portalu
|   \-- home.html            # Szablon agendy dla konkretnego miasta
|-- public/                  # GŁÓWNY KATALOG WYJŚCIOWY (BUILD). Statyczny HTML serwowany na produkcji
|   |-- assets/              # placeholder.svg i thumbnails/*.webp generowane przez scrapery
|   \-- [miasto]/            # Wygenerowane struktury HTML agendy, wydarzeń i miejsc
\-- docs/                    # PRZESTARZAŁY KATALOG. Ignoruj go przy buildzie i diagnozie

4. CYKL ŻYCIA DANYCH (FLOW) I ARCHITEKTURA OBRONNAOrkiestracja (run.py):Uruchomienie: python run.py --city [miasto] [--skip-enrich] [--docker].  Krok 1 (Contract Tests): Odpalenie pytest tests/test_contracts.py. Weryfikacja, czy zewnętrzni dostawcy nie zmienili klas w drzewie DOM.  Krok 2 (Preflight): src/main.py --preflight weryfikuje kody odpowiedzi HTTP wszystkich zarejestrowanych scraperów.  Scraping (Deep Scraping):Scrapery z src/infrastructure/scrapers/ pobierają listy, a następnie wchodzą na podstrony szczegółowe wydarzeń, aby wyciągnąć pełny opis, czas trwania, dokładną godzinę i cennik biletów.  Zewnętrzne grafiki są pobierane, konwertowane do formatu .webp (max szerokość 600px) i zapisywane lokalnie w public/assets/thumbnails/.  Bezpiecznik Wolumenu (Circuit Breaker w main.py):Każde źródło podlega walidacji minimalnego progu rekordów (MIN_THRESHOLDS). Jeśli scraper zwróci liczbę rekordów poniżej progu (np. 0 zamiast średnio 20), jego wynik jest odrzucany z błędem krytycznym, co chroni bazę przed nadpisaniem pustymi danymi.  Przetwarzanie (ETL w src/domain/pipeline.py):Sanityzacja Mojibake: Automatyczny rekursywny filtr clean_mojibake_deep usuwa rzeczywiste artefakty błędnego kodowania CP1250/CP852 (╣, Š, ŕ, │, ˝, ˇ, ť, č, ┐, ú, î, ľ, ô), nie uszkadzając poprawnych znaków diakrytycznych (Ć, ä, ö, â).  Dopasowanie OSM (_resolve_place): Mapowanie miejsca następuje wg hierarchii:Reguły jawne venue_match_rules w config/[miasto].yaml -> powiązanie z kluczem w data/[miasto]/places_clean.json.  Wyszukiwanie pełnotekstowe w korpusie tytułu i opisu.  Dopasowanie podobieństwa tekstu (_calculate_place_similarity, próg >= 0.75).  Logistyka miejska: Wyszukiwanie najbliższej gastronomii i parkingów w promieniu zdefiniowanym w konfiguracji.  Wzbogacanie (src/domain/enricher.py):Opcjonalna faza LLM/OCR (pomijana flagą --skip-enrich). Odpala RapidOCR na miniaturze i uzupełnia brakujące dane logistyczne.  Walidacja i Zapis (src/infrastructure/db.py):Rzutowanie na modele Pydantic (FullEventPage). Zapis kompletnych rekordów w formacie JSON w tabeli events bazy data/events.db.  Generowanie statyczne (Build w src/infrastructure/renderer.py):Odczyt zweryfikowanych rekordów z bazy, aplikacja filtrów dat (ukrywanie wydarzeń przeszłych), wstrzyknięcie do szablonów Jinja2 i zapis gotowych plików .html w katalogu public/[miasto]/.  5. TWARDE REGUŁY PROJEKTOWE (GUARDRAILS)A. Kodowanie i Obsługa HTTPDekodowanie HTML: W scraperach BeautifulSoup MUSI być inicjalizowany z surowej zawartości binarnej: BeautifulSoup(resp.content, "html.parser") lub z wymuszeniem resp.encoding = "utf-8". Użycie domyślnego BeautifulSoup(resp.text, ...) prowadzi do skażenia ISO-8859-1.  Parametry URL: W parametrach wyszukiwania (params / urljoin) należy stosować bezpieczne ciągi ASCII (np. "Bielsko" zamiast "Bielsko-Biała" w szukaj/?q=...), aby zapobiec podwójnemu kodowaniu znaków przez serwery docelowe[cite: 1].Pliki źródłowe: Wszystkie pliki .py, .yaml i .json w repozytorium muszą być zapisywane bezwzględnie w formacie UTF-8 bez BOM[cite: 1].B. Scrapery i Jakość DanychZakaz powierzchownego scrapingu (No Shallow Scraping): Scraper nie może wstawiać atrap jednolinijkowych typu Wydarzenie: {tytuł}[cite: 1]. Jeśli źródło udostępnia podstronę, scraper ma obowiązek pobrać z niej pełny opis, cennik i właściwy plakat[cite: 1].Odporność selektorów linków: Szukając linku do szczegółów na karcie wydarzenia, scraper musi iterować po dostępnych tagach <a> i ignorować przyciski funkcyjne (np. „Kup bilet”, „Więcej”, „Bilety”), aby nie przypisać pustego tytułu ani nie odrzucić poprawnego rekordu[cite: 1].Izolacja Cache: Przy debugowaniu scraperów lub przebudowie selektorów należy bezwzględnie usunąć data/http_cache.sqlite, aby nie przetwarzać zamrożonych stron z błędami[cite: 1].C. Miejsca i Konfiguracja (config/[miasto].yaml)Spójność z bazą miejsc: Każda reguła w venue_match_rules musi wskazywać na istniejący identyfikator target_id w data/[miasto]/places_clean.json[cite: 1].Zakaz sztucznych lokalizacji: Nigdy nie ustawiaj fallbacku lokalizacji na ogólną nazwę miasta (np. venue = 'Bielsko-Biała') ani na sztuczne byty ('Przestrzeń Miejska'), jeśli nie mają one bezpośredniego odzwierciedlenia w pliku places_clean.json[cite: 1].D. Frontend i Szablony (templates/)Model VOD (Ambient Backdrop): Strona wydarzenia (event_page.html) MUSI używać układu dwukolumnowego (treść po lewej, logistyka po prawej)[cite: 1]. Baner górny 16:9: tło to rozmyty plakat (filter: blur(25px)), pierwszy plan to wycentrowany, ostry, pionowy plakat (object-fit: contain)[cite: 1].Fallback grafik: Obsługiwany wyłącznie przez szablon: {{ event.image_url or '/assets/placeholder.svg' }}[cite: 1]. Scraper zwraca pusty ciąg "" w przypadku braku plakatu[cite: 1].Ścieżki statyczne: Zawsze stosuj ścieżki bezwzględne względem serwera HTTP (np. /assets/thumbnails/..., /bielsko_biala/...), nigdy ścieżek lokalnych systemu Windows[cite: 1].Zakaz edycji w public/: Wszelkie zmiany wizualne wprowadza się wyłącznie w templates/, a zmiany danych w logice scraperów/pipeline, po czym wykonuje się przebudowę przez run.py[cite: 1].