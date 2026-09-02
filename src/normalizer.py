from src.utils.helpers import slugify
from datetime import datetime
import re
import unicodedata
from typing import Dict, Any, List, Optional

from src.core.models import EventAnalysis, FullEventPage, QuickFacts, TicketInfo, NearbyGastro
from src.placeholders import generate_event_placeholder

POLISH_DAYS = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
POLISH_MONTHS_GEN = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]


def format_polish_date(date_iso: str) -> str:
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
        return f"{POLISH_DAYS[dt.weekday()]}, {dt.day} {POLISH_MONTHS_GEN[dt.month]}"
    except Exception:
        return date_iso


def normalize_ticket_price(raw_price: str, is_free_flag: bool = None, source_url: str = "") -> str:
    """
    Deterministyczny parser sprowadzający dowolny stan cennika do 5 czystych etykiet:
    - 'od X zł' / 'X zł' (kwoty konkretne)
    - 'Wstęp bezpłatny'
    - 'Bilety płatne'
    - 'Cennik obiektu'
    - 'Sprawdź szczegóły'
    """
    raw = (raw_price or "").strip()
    raw_lower = raw.lower()
    source_lower = (source_url or "").lower()

    if not raw and is_free_flag is not True:
        if "galeriabielska" in source_lower:
            return "Wstęp bezpłatny"
        if "mosir" in source_lower:
            return "Cennik obiektu"
        return "Sprawdź szczegóły"

    # 1. Wykrywanie konkretnych kwot
    match_od = re.search(r"od\s*([\d\s,.-]+)\s*zł", raw, re.IGNORECASE)
    if match_od:
        val = match_od.group(1).replace(" ", "").replace(",", ".")
        try:
            val_f = float(val)
            return f"od {val_f:.2f} zł".replace(".00", "")
        except ValueError:
            return f"od {match_od.group(1).strip()} zł"

    match_exact = re.search(r"^(\d+[\s,.-]*)\s*zł$", raw, re.IGNORECASE)
    if match_exact:
        return f"{match_exact.group(1).strip()} zł"

    # 2. Bezpłatność
    if is_free_flag is True or any(k in raw_lower for k in ["wstęp wolny", "bezpłatn", "wstęp bezpłatny"]):
        if not any(ign in raw_lower for ign in ["sprawdź", "kasa", "cennik"]):
            return "Wstęp bezpłatny"

    # 3. Bilety płatne
    if any(k in raw_lower for k in ["kupbilecik", "bilety24", "eventim", "bck bilety"]):
        return "Bilety płatne"
    if "bilety wyprzedane" in raw_lower:
        return "Bilety wyprzedane"

    # 4. Fallbacki
    if "galeriabielska" in source_lower or "wystaw" in raw_lower:
        return "Wstęp bezpłatny"
    if "mosir" in source_lower:
        return "Cennik obiektu"
    if any(k in raw_lower for k in ["sprawdź bilety", "kasa", "cennik", "sprawdź cennik"]):
        return "Sprawdź szczegóły"

    if any(k in raw_lower for k in ["bilety płatne", "biletowany", "płatn"]):
        return "Bilety płatne"

    return "Sprawdź szczegóły"


def create_event_record(event: dict, default_city_name: str = "Miasto") -> FullEventPage:
    title = event.get("title", "").strip()
    date_str = event.get("date_start") or event.get("date") or datetime.now().strftime("%Y-%m-%d")
    date_end = event.get("date_end") or date_str

    date_match = re.search(r"\d{4}-\d{2}-\d{2}", str(date_str))
    exact_date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
    date_formatted = format_polish_date(exact_date)

    category = event.get("category") or "Kultura i Rozrywka"
    title_lower = title.lower()
    if category in ["Kultura", "Kultura i Rozrywka"]:
        if any(k in title_lower for k in ["turniej", "sport", "bieg", "triathlon", "siatków", "orlik", "parkrun", "spływ", "rolk"]):
            category = "Sport i Rekreacja"
        elif any(k in title_lower for k in ["kino", "film"]):
            category = "Kino"
        elif any(k in title_lower for k in ["koncert", "muzyka", "cover", "dj", "festiwal", "fado"]):
            category = "Koncert"
        elif any(k in title_lower for k in ["bibliotek", "książk", "dzieci", "półkolonia", "lekcje", "bajk"]):
            category = "Dla Dzieci"

    slug = event.get("slug") or slugify(f"{exact_date}-{title[:35]}")
    desc = (event.get("description") or "").strip()
    desc = re.sub(r"^\[.*?\]:\s*", "", desc).strip()
    desc = re.sub(r"^Wydarzenie (?:w|sportowe MOSiR)?\s*[^:]+:\s*", "", desc, flags=re.IGNORECASE).strip()

    full_description = desc or f"Wydarzenie: {title}."
    first_sentence = full_description.split(". ")[0].strip()
    if len(first_sentence) > 180:
        editorial_lead = first_sentence[:180].rsplit(" ", 1)[0].rstrip(",-:") + "..."
    else:
        editorial_lead = first_sentence if first_sentence.endswith(".") else f"{first_sentence}."

    time_start = event.get("time_start") or "Według harmonogramu"
    if isinstance(event.get("analysis"), dict) and "ticket_info" in event["analysis"]:
        time_start = event["analysis"]["ticket_info"].get("time_start") or time_start

    venue = event.get("venue") or default_city_name
    address = event.get("address") or venue
    source_url = event.get("source_url") or event.get("url") or "#"
    source_name = event.get("source") or "portal"

    raw_price = event.get("price_range") or ""
    is_free = event.get("is_free")
    if isinstance(event.get("analysis"), dict) and "ticket_info" in event["analysis"]:
        raw_price = event["analysis"]["ticket_info"].get("price_range") or raw_price
        is_free = event["analysis"]["ticket_info"].get("is_free", is_free)

    price_range = normalize_ticket_price(raw_price, is_free_flag=is_free, source_url=source_url)

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
            f"Bilety / Wstęp: {price_range}",
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
            price_range=price_range,
            place_id=event.get("place_id")
        ),
        address=address
    )

    return FullEventPage(
        slug=slug,
        title=title,
        date_start=exact_date,
        date_end=date_end,
        date_formatted=date_formatted,
        image_url=image_url,
        source_url=source_url,
        place_id=event.get("place_id"),
        analysis=analysis,
        nearby_gastro=[]
    )

def format_event_description(text: str) -> str:
    if not text:
        return ""
    
    t = str(text).replace("\r", " ").replace("\t", " ")
    t = re.sub(r'<br\s*/?>', '\n', t, flags=re.IGNORECASE)
    t = re.sub(r'[ \u202f\u200b]', ' ', t)

    # 1. Usuwanie spamu SEO ("- więcej informacji") wraz z powtórzonym tytułem i emoji
    target = "więcej informacji"
    while target in t.lower():
        pos = t.lower().find(target)
        # Szukamy początku wstrzyknięcia wstecz (do 250 znaków)
        start_search = max(0, pos - 250)
        prefix = t[start_search:pos]
        
        # Szukamy klastra emoji lub znaku interpunkcyjnego
        emoji_matches = list(re.finditer(r'[\U00010000-\U0010ffff\u2600-\u27ff]+', prefix))
        punc_matches = list(re.finditer(r'[\.!\?\n]', prefix))
        
        if emoji_matches:
            cut_start = start_search + emoji_matches[-1].start()
        elif punc_matches:
            cut_start = start_search + punc_matches[-1].end()
        else:
            cut_start = max(0, pos - 60)
            
        t = t[:cut_start].rstrip(" .-\t") + ". " + t[pos + len(target):].lstrip(" .-\t")

    # 2. Standaryzacja etykiet metadanych
    for lbl in META_LABELS:
        pattern = r'(?<!\n)\b' + re.escape(lbl) + r'\s*:'
        t = re.sub(pattern, f'\n\n* **{lbl}:**', t)

    # 3. Wyodrębnienie P.S. i komunikatów specjalnych
    t = re.sub(r'(?<!\n)\s*(P\.S\..*)$', r'\n\n\1', t, flags=re.IGNORECASE)
    t = re.sub(r'(?<!\n)\s*(UWAGA!?:?|INFORMACJE ORGANIZACYJNE:?|WAŻNE:?)', r'\n\n\1', t, flags=re.IGNORECASE)

    # Czyszczenie zbiegów kropek i spacji
    t = re.sub(r'\s*\.\s*\.', '.', t)
    t = re.sub(r'[ ]{2,}', ' ', t)

    # 4. Dynamiczny podział na akapity (~160-240 znaków)
    raw_blocks = [b.strip() for b in t.split("\n") if b.strip()]
    final_paragraphs = []

    for block in raw_blocks:
        if block.startswith("*") or block.startswith("-"):
            final_paragraphs.append(block)
            continue

        sentences = [s.strip() for s in re.split(r'(?<=[.!?…])\s+', block) if s.strip()]
        curr_buf = []
        curr_len = 0

        for s in sentences:
            if s.upper().startswith("P.S.") or s.upper().startswith("UWAGA"):
                if curr_buf:
                    final_paragraphs.append(" ".join(curr_buf))
                    curr_buf, curr_len = [], 0
                final_paragraphs.append(s)
                continue

            curr_buf.append(s)
            curr_len += len(s)

            if curr_len >= 160:
                final_paragraphs.append(" ".join(curr_buf))
                curr_buf, curr_len = [], 0

        if curr_buf:
            final_paragraphs.append(" ".join(curr_buf))

    return "\n\n".join(final_paragraphs)
