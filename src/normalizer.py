from datetime import datetime
import re
import unicodedata

from src.models import EventAnalysis, FullEventPage, QuickFacts, TicketInfo
from src.placeholders import generate_event_placeholder

POLISH_DAYS = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Ndz"]
POLISH_MONTHS_GEN = ["", "sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def format_polish_date(date_iso: str) -> str:
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
        return f"{POLISH_DAYS[dt.weekday()]}, {dt.day} {POLISH_MONTHS_GEN[dt.month]}"
    except Exception:
        return date_iso


def create_event_record(event: dict, default_city_name: str = "Miasto") -> FullEventPage:
    title = event.get("title", "").strip()
    date_str = event.get("date", datetime.now().strftime("%Y-%m-%d"))

    date_match = re.search(r"\d{4}-\d{2}-\d{2}", date_str)
    exact_date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
    date_formatted = format_polish_date(exact_date)

    category = "Kultura"
    title_lower = title.lower()
    if any(k in title_lower for k in ["turniej", "sport", "bieg", "triathlon", "siatków", "orlik", "parkrun", "spływ", "rolk"]):
        category = "Sport"
    elif any(k in title_lower for k in ["kino", "film"]):
        category = "Kino"
    elif any(k in title_lower for k in ["koncert", "muzyka", "cover", "dj", "festiwal", "fado"]):
        category = "Koncert"
    elif any(k in title_lower for k in ["bibliotek", "książk", "dzieci", "półkolonia", "lekcje", "bajk", "plener"]):
        category = "Dla Dzieci"

    slug = slugify(f"{exact_date}-{title[:35]}")
    desc = (event.get("description") or "").strip()
    desc = re.sub(r"^\[.*?\]:\s*", "", desc).strip()

    full_description = desc or f"Wydarzenie miejskie: {title}."

    first_sentence = full_description.split(". ")[0].strip()
    if len(first_sentence) > 200:
        editorial_lead = first_sentence[:200].rsplit(" ", 1)[0].rstrip(",-:") + "..."
    else:
        editorial_lead = first_sentence if first_sentence.endswith(".") else f"{first_sentence}."

    time_start = event.get("time_start", "Według harmonogramu")
    venue = event.get("venue", default_city_name)
    address = event.get("address", venue)
    price_range = event.get("price_range", "Sprawdź bilety / Wstęp wolny")
    source_name = event.get("source", "portal")

    raw_img = event.get("image_url", "")
    if not raw_img or "unsplash.com" in raw_img:
        image_url = generate_event_placeholder(title=title, category=category)
    else:
        image_url = raw_img

    organizer = event.get("organizer") or ("Miejski Ośrodek Kultury" if "mok" in source_name else default_city_name)

    analysis = EventAnalysis(
        category=category,
        badges=[category, source_name],
        organizer=organizer,
        editorial_lead=editorial_lead,
        full_description=full_description,
        details_bullets=[
            f"Lokalizacja: {venue}",
            f"Godzina rozpoczęcia: {time_start}",
            f"Cena / Bilety: {price_range}",
            "Więcej informacji na oficjalnej stronie organizatora"
        ],
        quick_facts=QuickFacts(
            duration="~2h",
            age_rating="Wszyscy",
            parking="Dostępny w pobliżu obiektu"
        ),
        ticket_info=TicketInfo(
            time_start=time_start,
            venue_name=venue,
            price_range=price_range
        ),
        address=address
    )

    return FullEventPage(
        slug=slug,
        title=title,
        date_start=exact_date,
        date_end=exact_date,
        date_formatted=date_formatted,
        image_url=image_url,
        source_url=event.get("url", "#"),
        analysis=analysis
    )