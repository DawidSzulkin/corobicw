from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class EventContract:
    """
    Uniwersalny standard danych dla dowolnego wydarzenia (koncert, wystawa, plener, stand-up).
    Bazowa klasa dla wszystkich scraperów w systemie.
    """

    # --- 1. IDENTYFIKACJA I ŹRÓDŁO ---
    title: str                                          # Czysty tytuł wydarzenia
    date_start: str                                     # RRRR-MM-DD (ISO)
    time_start: Optional[str] = None                    # GG:MM (np. "19:00") lub None
    date_end: Optional[str] = None                      # RRRR-MM-DD (dla wystaw i festiwali)
    time_end: Optional[str] = None                      # GG:MM
    source_url: str = ""                                # Bezpośredni link do podstrony wydarzenia
    source: str = ""                                    # Identyfikator scrapera (np. "galeriabielska_pl", "ncpp_opole_pl")
    external_id: Optional[str] = None                   # ID w systemie źródłowym (np. ID w Biletynie)

    # --- 2. LOKALIZACJA I BUDYNEK ---
    venue: str = ""                                     # Oficjalna nazwa obiektu / instytucji
    stage_name: Optional[str] = None                    # Dokładna nazwa sali / sceny / galerii
    address: str = ""                                   # Pełny adres (ulica, numer, miasto)
    city: str = ""                                      # Slug miasta (np. "bielsko_biala", "opole", "kedzierzyn_kozle")

    # --- 3. KATEGORYZACJA I TYP ---
    category: str = "other"                             # "theatre", "concert", "exhibition", "cinema", "kids", "comedy", "workshop", "outdoor"
    tags: List[str] = field(default_factory=list)       # np. ["premiera", "darmowe", "festiwal"]

    # --- 4. DOSTĘPNOŚĆ BUDYNKU I CYFROWA (TRZYSTANOWA) ---
    # True = Dostępne, False = Niedostępne, None = Brak danych / Niezweryfikowane
    wheelchair_accessible: Optional[bool] = None        # Wjazd bez barier / winda / podjazd
    hearing_loop: Optional[bool] = None                 # Pętla indukcyjna dla aparatów słuchowych
    pjm_translation: bool = False                       # Tłumaczenie na Polski Język Migowy
    audio_description: bool = False                     # Audiodeskrypcja dla osób niewidomych
    subtitles_lang: Optional[str] = None                # Napisy: "pl", "en", "uk" lub None
    box_office_phone: Optional[str] = None              # Telefon do kasy (np. rezerwacja miejsc dla OzN)

    # --- 5. LOGISTYKA, CZAS I OBOSTRZENIA ---
    duration_str: Optional[str] = None                  # Czysty czas trwania: "90 min", "120 min"
    interval_str: str = "Brak"                          # "1 przerwa", "2 przerwy" lub "Brak"
    age_limit: Optional[str] = None                     # "18+", "16+", "12+", "Dla dzieci" lub None
    warnings: List[str] = field(default_factory=list)   # ["światła stroboskopowe", "dym sceniczny", "głośny dźwięk", "nagość"]

    # --- 6. BILETY I TRANSAKCJE ---
    price_range: str = "Bilety płatne"                  # "Bilety płatne", "Wstęp wolny", "Bilety wyprzedane"
    ticket_url: Optional[str] = None                    # Bezpośredni URL do zakupu biletu
    is_free: bool = False                               # True jeśli wstęp wolny / bezpłatny
    is_sold_out: bool = False                           # True jeśli bilety zostały wyprzedane
    ticket_offers: List[Dict[str, Any]] = field(default_factory=list) # Zgodne z kontraktem ticket_offers w bazie

    # --- 7. TREŚĆ I MULTIMEDIA ---
    description: str = ""                               # Czysty opis merytoryczny wydarzenia
    image_url: Optional[str] = None                     # Plakat / grafika w wysokiej rozdzielczości
    organizer: Optional[str] = None                     # Nazwa organizatora (jeśli inna niż venue)

    def to_dict(self) -> Dict[str, Any]:
        """Konwersja do słownika zgodnego z silnikiem bazy danych i rendererem."""
        venue_display = f"{self.venue} ({self.stage_name})" if (self.stage_name and self.stage_name != self.venue) else self.venue
        
        # Automatyczne budowanie ticket_offers jeśli podano ticket_url
        offers = list(self.ticket_offers)
        if self.ticket_url and not offers:
            offers.append({
                "provider": self.source,
                "url": self.ticket_url,
                "price": self.price_range,
                "raw_price": self.price_range,
                "is_primary": True,
                "discounts": []
            })

        return {
            "title": self.title,
            "date_start": self.date_start,
            "date_end": self.date_end or self.date_start,
            "time_start": self.time_start or "",
            "time_end": self.time_end or "",
            "venue": venue_display,
            "stage_name": self.stage_name or "",
            "address": self.address,
            "city": self.city,
            "category": self.category,
            "tags": self.tags,
            "price_range": "Wstęp wolny" if self.is_free else self.price_range,
            "is_free": self.is_free,
            "is_sold_out": self.is_sold_out,
            "ticket_url": self.ticket_url,
            "ticket_offers": offers,
            "description": self.description,
            "duration_str": self.duration_str,
            "interval_str": self.interval_str,
            "age_limit": self.age_limit,
            "warnings": self.warnings,
            "wheelchair_accessible": self.wheelchair_accessible,
            "hearing_loop": self.hearing_loop,
            "pjm_translation": self.pjm_translation,
            "audio_description": self.audio_description,
            "subtitles_lang": self.subtitles_lang,
            "box_office_phone": self.box_office_phone,
            "image_url": self.image_url,
            "source_url": self.source_url,
            "source": self.source,
            "organizer": self.organizer or self.venue,
            "external_id": self.external_id
        }


@dataclass
class ShowContract(EventContract):
    """
    Rozszerzony kontrakt dedykowany dla teatrów, oper i filharmonii.
    Zachowuje 100% kompatybilności wstecznej z istniejącym kodem.
    """
    category: str = "theatre"
    premiere_date: Optional[str] = None                 # Data premiery (np. "14.12.2024")
    creators: List[Dict[str, str]] = field(default_factory=list) # [{"role": "Reżyseria", "name": "..."}]
    cast: List[Dict[str, str]] = field(default_factory=list)     # [{"character": "Hamlet", "actor": "..."}]

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "premiere_date": self.premiere_date,
            "creators": self.creators,
            "cast": self.cast
        })
        return data