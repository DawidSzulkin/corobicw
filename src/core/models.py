from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class QuickFacts(BaseModel):
    duration: str = "~2h"
    age_rating: str = "Wszyscy"
    parking: str = "Dostępny w pobliżu obiektu"


class TicketInfo(BaseModel):
    time_start: str
    venue_name: str
    price_range: str
    doors_open: Optional[str] = None
    place_id: Optional[str] = None


class NearbyGastro(BaseModel):
    place_id: str
    name: str
    distance_m: int
    walk_time_min: int
    category: str


class TicketOffer(BaseModel):
    provider: str
    url: str
    price: Optional[str] = None
    is_primary: bool = False
    tag: Optional[str] = None
    tag_class: Optional[str] = None
    discounts: list[dict[str, Any]] = []

class EventAnalysis(BaseModel):
    category: str
    badges: List[str]
    organizer: str
    editorial_lead: str
    full_description: str
    details_bullets: List[str]
    quick_facts: QuickFacts
    ticket_info: TicketInfo
    address: str


class FullEventPage(BaseModel):
    is_cancelled: bool = False
    slug: str
    title: str
    date_start: str
    date_end: str
    date_formatted: str
    image_url: str
    source_url: str
    place_id: Optional[str] = None
    analysis: EventAnalysis
    nearby_gastro: List[NearbyGastro] = []
    ticket_offers: List[TicketOffer] = []

