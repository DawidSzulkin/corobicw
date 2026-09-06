from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class ShowContract:
    """
    Ujednolicony standard danych spektaklu dla dowolnego teatru w Polsce.
    Każdy nowy scraper MUSI mapować pobrane dane do tego schematu.
    """

    # --- 1. IDENTYFIKACJA WYDARZENIA ---
    title: str                                # Czysty tytuł spektaklu (bez "Premiera!", bez cudzysłowów)
    date_start: str                           # RRRR-MM-DD (ISO)
    time_start: str                           # GG:MM (np. "19:00")
    source_url: str                           # Bezpośredni link do podstrony spektaklu
    source: str                               # Identyfikator scrapera (np. "teatr_bielsko_pl", "teatr_slaski_katowice")

    # --- 2. LOKALIZACJA I BUDYNEK (POZIOM SCENY) ---
    venue: str                                # Oficjalna nazwa teatru (np. "Teatr Polski w Bielsku-Białej")
    stage_name: str                           # Dokładna nazwa sali: "Duża Scena", "Mała Scena", "Scena Kameralna"
    address: str                              # Pełny adres z miastem
    city: str                                 # Slug miasta (np. "bielsko_biala", "katowice")

    # --- 3. DOSTĘPNOŚĆ BUDYNKU (DETERMINISTYCZNA ZE SCENY) ---
    # Nigdy nie parsuj tego tekstem z opisów spektaklu. Przypisuj na podstawie stage_name i Deklaracji Dostępności teatru.
    wheelchair_accessible: bool = False       # True TYLKO gdy na salę jest wjazd bez barier / platforma
    hearing_loop: bool = False                # True TYLKO gdy sala posiada działającą pętlę indukcyjną dla aparatów słuchowych
    box_office_phone: Optional[str] = None    # Telefon kasy (niezbędny do rezerwacji miejsc na wózki)

    # --- 4. PARAMETRY CZASOWO-MERYTORYCZNE SPEKTAKLU ---
    duration_str: Optional[str] = None        # Sam czysty czas: "150 min", "90 min" (bez nawiasów z przerwami)
    interval_str: str = "Brak"                # "1 przerwa", "2 przerwy" lub "Brak"
    premiere_date: Optional[str] = None       # Data premiery jako element metryczki (np. "14.12.2024")

    # --- 5. OSTRZEŻENIA I OGRANICZENIA TREŚCIOWE ---
    age_limit: Optional[str] = None           # "18+", "16+", "12+", "Dla dzieci" lub None
    warnings: List[str] = field(default_factory=list) 
    # Dopuszczalne triggery: "światła stroboskopowe", "dym sceniczny", "dosadny język", "efekty hukowe / wystrzały", "nagość"

    # --- 6. TREŚĆ I MULTIMEDIA ---
    description: str = ""                     # Czysta fabuła bez numerów kont, cookies, regulaminów i telefonów kasy
    image_url: Optional[str] = None           # Plakat w wysokiej rozdzielczości (zapisany lokalnie lub link CDN)
    price_range: str = "Bilety płatne"        # "Bilety płatne", "Wstęp wolny", "Bilety wyprzedane"

    # --- 7. ZESPÓŁ ARTYSTYCZNY (STRUKTURA LISTY SŁOWNIKÓW) ---
    # Format: [{"role": "Reżyseria", "name": "Jan Kowalski"}]
    creators: List[Dict[str, str]] = field(default_factory=list)

    # Format: [{"character": "Hamlet", "actor": "Piotr Nowak"}]
    # Muzycy: [{"character": "Muzyk (fortepian)", "actor": "Adam Małysz"}] - imię wykonawcy ZAWSZE czyste w polu actor
    cast: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Konwersja do słownika zgodnego z silnikiem bazy danych portalu."""
        return {
            "title": self.title,
            "date_start": self.date_start,
            "date_end": self.date_start,
            "time_start": self.time_start,
            "venue": f"{self.venue} ({self.stage_name})" if self.stage_name else self.venue,
            "stage_name": self.stage_name,
            "address": self.address,
            "city": self.city,
            "price_range": self.price_range,
            "description": self.description,
            "duration_str": self.duration_str,
            "interval_str": self.interval_str,
            "premiere_date": self.premiere_date,
            "age_limit": self.age_limit,
            "warnings": self.warnings,
            "wheelchair_accessible": self.wheelchair_accessible,
            "hearing_loop": self.hearing_loop,
            "box_office_phone": self.box_office_phone,
            "creators": self.creators,
            "cast": self.cast,
            "image_url": self.image_url,
            "source_url": self.source_url,
            "source": self.source,
            "organizer": self.venue
        }
