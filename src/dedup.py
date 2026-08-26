import re
from difflib import SequenceMatcher
from typing import Any, Dict, List


def normalize_title(text: str) -> str:
    """Usuwa znaki specjalne, roczniki i normalizuje tekst do porównania."""
    text = text.lower()
    text = re.sub(r"\b20\d{2}\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 1]
    return " ".join(tokens)


def _extract_date(event: Dict[str, Any]) -> str:
    date_val = str(event.get("date_start") or event.get("date") or "").strip()
    return date_val[:10]


def is_same_event(ev1: Dict[str, Any], ev2: Dict[str, Any], threshold: float = 0.65) -> bool:
    """Sprawdza, czy dwa rekordy to to samo wydarzenie (musi zgadzać się dzień + podobieństwo tytułu)."""
    d1 = _extract_date(ev1)
    d2 = _extract_date(ev2)
    if not d1 or not d2 or d1 != d2:
        return False

    t1 = normalize_title(ev1.get("title", ""))
    t2 = normalize_title(ev2.get("title", ""))

    if not t1 or not t2:
        return False

    if t1 == t2 or t1 in t2 or t2 in t1:
        return True

    ratio = SequenceMatcher(None, t1, t2).ratio()
    return ratio >= threshold


def merge_event_records(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """Łączy dwa rekordy, dając priorytet danym niepustym i o wyższej jakości."""
    merged = dict(secondary)
    for k, v in primary.items():
        if v is not None and v != "":
            merged[k] = v

    # Zachowaj dłuższy i pełniejszy opis
    desc1 = primary.get("description") or primary.get("analysis", {}).get("full_description", "")
    desc2 = secondary.get("description") or secondary.get("analysis", {}).get("full_description", "")
    if desc1 and desc2:
        merged["description"] = desc1 if len(desc1) >= len(desc2) else desc2
    elif desc1 or desc2:
        merged["description"] = desc1 or desc2

    # Wybierz konkretną cenę zamiast wartości domyślnej
    p1 = primary.get("price_range") or primary.get("analysis", {}).get("ticket_info", {}).get("price_range", "")
    p2 = secondary.get("price_range") or secondary.get("analysis", {}).get("ticket_info", {}).get("price_range", "")
    if p1 and "sprawdź" not in str(p1).lower():
        merged["price_range"] = p1
    elif p2:
        merged["price_range"] = p2

    # Preferuj oryginalny plakat zamiast domyślnego Unsplash
    img1 = str(primary.get("image_url", ""))
    img2 = str(secondary.get("image_url", ""))
    if img1 and "unsplash" not in img1:
        merged["image_url"] = img1
    elif img2:
        merged["image_url"] = img2

    return merged


def deduplicate_events(events_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplikuje listę wydarzeń z różnych źródeł."""
    unique_events: List[Dict[str, Any]] = []

    for event in events_list:
        matched = False
        for i, existing in enumerate(unique_events):
            if is_same_event(event, existing):
                unique_events[i] = merge_event_records(event, existing)
                matched = True
                break

        if not matched:
            unique_events.append(event)

    return unique_events
