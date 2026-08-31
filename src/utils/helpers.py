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

