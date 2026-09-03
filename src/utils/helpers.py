import math
import re
import unicodedata


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Oblicza odległość ortodromiczną (w metrach) między dwoma punktami na Ziemi."""
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def slugify(text: str) -> str:
    """Konwertuje ciąg znaków na bezpieczny URL-slug."""
    if not text:
        return ""
    text = text.replace("ł", "l").replace("Ł", "L").replace("ó", "o").replace("Ó", "O")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text).strip("-")


def normalize_title(text: str, city: str = "") -> str:
    """Normalizuje tytuł wydarzenia dla celów deduplikacji."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"20\d{2}", "", text)

    if city and city != "unknown":
        text = re.sub(rf"{re.escape(city.lower())}", "", text)

    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 1]
    return " ".join(sorted(tokens))



# --- CENTRALNY SYSTEM IDENTYFIKACJI I AUTORYTETU DOSTAWCÓW BILETÓW ---
KNOWN_AGGREGATORS = {
    "kupbilecik.pl": "KupBilecik",
    "biletyna.pl": "Biletyna",
    "ebilet.pl": "eBilet",
    "eventim.pl": "Eventim",
    "goingapp.pl": "Going.",
    "ticketmaster.pl": "Ticketmaster",
    "kicket.com": "kicket",
    "biletomat.pl": "Biletomat"
}

INSTITUTION_DOMAINS = {
    "bilety.ncpp.opole.pl": "NCPP Opole",
    "ncpp.opole.pl": "NCPP Opole",
    "cavatinahall.pl": "Cavatina Hall",
    "bck.bielsko.pl": "BCK Bielsko",
    "teatrpolski.bielsko.pl": "Teatr Polski",
    "teatr.bielsko.pl": "Teatr Polski",
    "teatrbanialuka.pl": "Teatr Lalek Banialuka",
    "banialuka.pl": "Teatr Lalek Banialuka",
    "galeriabielska.pl": "Galeria Bielska BWA",
    "mokkkozle.pl": "MOK Kędzierzyn-Koźle",
    "mok-kkozle.pl": "MOK Kędzierzyn-Koźle",
    "mosirkk.pl": "MOSiR Kędzierzyn-Koźle",
    "mbpkk.pl": "MBP Kędzierzyn-Koźle"
}

def resolve_ticket_provider(url: str, organizer: str = "") -> tuple[int, str, bool]:
    """
    Zwraca krotkę: (priorytet_autorytetu, nazwa_dostawcy, czy_oficjalna_kasa).
    Hierarchia:
      100: Oficjalna kasa instytucji
       80: Autoryzowane bileterie ogólnopolskie
       10: Pozostałe źródła
    """
    if not url:
        return (10, organizer or "Bilety", False)
        
    u_lower = url.lower().strip()
    try:
        parsed = urllib.parse.urlparse(u_lower)
        netloc = (parsed.netloc or "").split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
    except Exception:
        netloc = u_lower

    # 1. Instytucje: sortujemy klucze malejąco po długości (subdomeny pierwsze)
    for domain, name in sorted(INSTITUTION_DOMAINS.items(), key=lambda x: len(x[0]), reverse=True):
        if netloc == domain or netloc.endswith("." + domain) or domain in u_lower:
            return (100, name, True)
            
    # Słowa kluczowe w domenach instytucjonalnych
    if any(k in netloc for k in ["teatr", "filharmonia", "opera", "amfiteatr"]) and not any(a in netloc for a in KNOWN_AGGREGATORS):
        name = organizer.strip() if organizer else "Oficjalna kasa"
        return (100, name, True)

    # 2. Agregatory komercyjne
    for domain, name in sorted(KNOWN_AGGREGATORS.items(), key=lambda x: len(x[0]), reverse=True):
        if netloc == domain or netloc.endswith("." + domain) or domain in u_lower:
            return (80, name, False)

    # 3. Fallback: znany organizator
    if organizer and len(organizer.strip()) > 2:
        return (100, organizer.strip(), True)

    return (10, "Bilety", False)

def resolve_ticket_provider(url: str, organizer: str = "") -> tuple[int, str, bool]:
    """
    Zwraca krotkę: (priorytet_autorytetu, nazwa_dostawcy, czy_oficjalna_kasa).
    Hierarchia autorytetu:
      100: Oficjalna kasa / Organizator instytucjonalny
       80: Bileterie ogólnopolskie partnerskie (KupBilecik, Biletyna itd.)
       10: Nieznane źródła zewnętrzne
    """
    if not url:
        return (10, organizer or "Bilety", False)
        
    u_lower = url.lower()
    
    # 1. Sprawdzenie instytucji kultury (Official Box Office)
    for domain, name in INSTITUTION_DOMAINS.items():
        if domain in u_lower:
            return (100, name, True)
            
    # Słowa kluczowe w domenach instytucji
    if any(k in u_lower for k in ["teatr", "filharmonia", "opera", "amfiteatr", "bilety."]) and not any(a in u_lower for a in KNOWN_AGGREGATORS):
        name = organizer.strip() if organizer else "Oficjalna kasa"
        return (100, name, True)
        
    # 2. Sprawdzenie komercyjnych pośredników
    for domain, name in KNOWN_AGGREGATORS.items():
        if domain in u_lower:
            return (80, name, False)
            
    # 3. Fallback: jeśli znamy organizatora, to on ma autorytet
    if organizer and len(organizer.strip()) > 2:
        return (100, organizer.strip(), True)
        
    return (10, "Bilety", False)
