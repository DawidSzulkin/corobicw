# PROJEKT: CoRobićW - Architektura, Kontekst i Protokół Operacyjny

Jesteś asystentem AI pracującym nad kodem dla lokalnego agregatora wydarzeń "CoRobićW". Traktuj ten dokument jako absolutne źródło prawdy o strukturze, logice projektu i zasadach współpracy.

---

## 1. PROTOKÓŁ KOMUNIKACJI (ZASADA ZERO)

Głównym kanałem naszej współpracy jest konsola **PowerShell**. Masz działać według ścisłej pętli:
1. Diagnoza przed akcją: Zanim zaproponujesz zmianę w kodzie, zawsze wygeneruj skrypt diagnostyczny (np. Get-Content, przeszukiwanie logów, sprawdzanie struktury), aby zorientować się w rzeczywistym stanie plików.
2. Automatyzacja schowka: Każdy skrypt diagnostyczny, który generujesz i z którego wynik chcesz zobaczyć, musi automatycznie kopiować wynik do schowka (| Set-Clipboard), abym mógł go od razu wkleić w czat.
3. Pętla operacyjna: Ty podajesz skrypt -> ja go odpalam -> wklejam Ci wynik -> Ty analizujesz -> podajesz kod naprawczy/kolejny krok.
4. Brak założeń: Nie zgaduj struktury plików ani zawartości klas. Jeśli czegoś nie wiesz, daj skrypt czytający ten konkretny plik.

---

## 2. STOS TECHNOLOGICZNY I ARCHITEKTURA

* Wzorzec: Static Site Generator (SSG) zasilany zautomatyzowanym potokiem ETL (Extract, Transform, Load).
* Język: Python 3.x.
* Baza danych: Lokalne środowisko SQLite (data/portal.db - główna, data/events.db - cache, data/http_cache.sqlite - requests cache).
* Renderowanie: Jinja2 (silnik generujący statyczny HTML).
* Wzbogacanie danych (AI/OCR): RapidOCR do odczytu tekstów z plakatów + lokalny model LLM (Ollama) do strukturyzacji opisów i wydobywania brakujących informacji organizacyjnych.

---

## 3. MAPA KATALOGÓW (ZORIENTOWANIE W PRZESTRZENI)

Drzewo projektu ma sztywny podział ról. Nie twórz plików w złych miejscach.

C:\Users\SZULKIN-KOMPUTER\Desktop\portal\
├── config/                  # Konfiguracje miast w YAML (opole.yaml, bielsko_biala.yaml, kedzierzyn_kozle.yaml)
├── data/                    # Bazy SQLite oraz pliki przejściowe JSON
│   ├── [miasto]/            # Surowe bazy miejsc (places_raw.json, places_clean.json)
│   ├── processed/           # Oczyszczone i przetworzone zrzuty ze scraperów
│   └── raw/                 # Surowe zrzuty scrapowanych danych z danego dnia
├── scripts/                 # Narzędzia developerskie, diagnostyka, jednorazowe fixy bazy (np. purge_garbage.py, fix_bom_and_test.py)
├── src/                     # GŁÓWNY KOD BACKENDU (PYTHON)
│   ├── core/                # models.py: Modele domenowe Pydantic (FullEventPage, EventAnalysis, QuickFacts). Wymuszają walidację.
│   ├── domain/              #
│   │   ├── pipeline.py      # GŁÓWNY SILNIK ETL: Pobiera, deduplikuje, dopasowuje geolokalizację (haversine) i składa obiekty.
│   │   └── enricher.py      # Moduł wywołujący OCR i LLM (Ollama) do poprawy jakości opisów wydarzeń.
│   ├── infrastructure/      #
│   │   ├── db.py            # Warstwa SQLite (operacje CRUD, init bazy).
│   │   ├── renderer.py      # Klasa HTMLRenderer. Most między bazą a szablonami Jinja.
│   │   └── scrapers/        # Skrypty agregujące per miasto/kraj (Dziedziczą po base.py).
│   ├── main.py              # ENTRYPOINT: Czyta config, inicjalizuje DB, odpala pipeline i wywołuje renderera.
│   ├── normalizer.py        # Logika normalizacji stringów, dat (format polski) i adresów.
│   └── placeholders.py      # Definiowanie awaryjnych stanów danych.
├── templates/               # GŁÓWNE SZABLONY FRONTENDOWE (JINJA2). Tu modyfikujemy wygląd.
│   ├── event_page.html      # Szablon strony pojedynczego wydarzenia.
│   ├── place_page.html      # Szablon strony obiektu/miejsca.
│   ├── portal_hub.html      # Landing page portalu.
│   └── home.html            # Szablon agendy dla konkretnego miasta.
├── public/                  # GŁÓWNY KATALOG WYJŚCIOWY (BUILD). Tutaj ląduje statyczny HTML.
│   ├── assets/              # placeholder.svg i thumbnails/*.webp generowane przez scrapery.
│   └── [miasto]/            # Wygenerowane struktury HTML agendy, wydarzeń i miejsc.
└── docs/                    # PRZESTARZAŁY KATALOG. Ignoruj go przy buildzie i diagnozie.

---

## 4. CYKL ŻYCIA DANYCH (FLOW) I POWIĄZANIA

1. Start: Uruchomienie python src/main.py.
2. Scraping: Moduł src/infrastructure/scrapers/registry.py rejestruje instancje klas scraperów dla danego miasta. Scrapery łączą się przez HTTP, zrzucają plakaty jako *.webp do /assets/thumbnails/ i formują surowe JSON-y.
3. Przetwarzanie (ETL): src/domain/pipeline.py przejmuje JSON-y. Wykrywa duplikaty (SequenceMatcher). Jeśli event ma adres, pipeline.py szuka w data/[miasto]/places_clean.json najbliższego miejsca, a następnie w promieniu X metrów szuka parkingów i restauracji z mapy OSM (OpenStreetMap).
4. Wzbogacanie: src/domain/enricher.py znajduje puste opisy lub braki logistyczne. Odpala RapidOCR na plakacie (*.webp) i wysyła zapytanie do Ollama, by wygenerować ustrukturyzowany tekst.
5. Walidacja: Dane są rzutowane na klasy z src/core/models.py. Błąd rzutowania odrzuca rekord.
6. Zapis: Zweryfikowane obiekty zapisywane są przez src/infrastructure/db.py w portal.db.
7. Generowanie (Build): src/infrastructure/renderer.py wstrzykuje zawartość z portal.db do szablonów z templates/ i zapisuje gotowe pliki .html w public/.

---

## 5. TWARDE REGUŁY PROJEKTOWE (GUARDRAILS)

### A. Frontend i Szablony (templates/)
* Model VOD (Ambient Backdrop): Strona wydarzenia (event_page.html) MUSI używać układu dwukolumnowego (treść po lewej, logistyka po prawej). Grafika główna to górny, poziomy baner 16:9, w którym tło to rozmyty plakat (filter: blur(25px)), a na 1. planie wycentrowany, ostry, pionowy plakat (object-fit: contain). Żadnego przycinania plakatów!
* Fallback grafik: NIGDY nie używaj sztywnych linków z zewnątrz (np. do Unsplash) jako fallbacków. Fallback obsługuje Jinja: {{ event.image_url or '/assets/placeholder.svg' }}. Scrapery z Pythona mają zwracać pustą wartość None, jeśli obrazu nie ma na stronie źródłowej.
* Ścieżki statyczne: Zawsze używamy ścieżek bezwzględnych względem root serwera (np. /assets/placeholder.svg), a nie ścieżek z dysku Windows (C:\...).

### B. Modyfikacje Backendu i Systemu
* BOM i kodowanie: Wszystkie operacje plikowe w PowerShell i Pythonie muszą wymuszać czyste UTF-8 bez BOM (encoding='utf-8'). Złe kodowanie wysadzi parser Jinja.
* Edycja w miejscu: Generator w Pythonie ciągle nadpisuje zawartość katalogu public/. Jeśli chcesz zmienić cokolwiek w strukturze strony, edytujesz tylko pliki w templates/, a następnie nakazujesz mi uruchomić przebudowę (python src/main.py). Zmiana pliku bezpośrednio w public/ jest stratą czasu, bo następny build ją zniszczy.
* Aktualizacje bazy: Jeśli modyfikujesz logikę w normalizer.py lub w scraperach, stare rekordy w bazie portal.db nie naprawią się same. Trzeba dać mi komendę na wyczyszczenie / drop tabel i puszczenie pipeline na nowo.
