import re
from difflib import SequenceMatcher
from typing import Any, Dict, List


def normalize_title(text: str) -> str:
    """Usuwa znaki specjalne, roczniki, cudzysłowy i normalizuje tekst do porównania."""
    text = text.lower()
    # Usunięcie roku (np. 2026) i interpunkcji
    text = re.sub(r"\b20\d{2}\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 2]
    return " ".join(tokens)


def is_same_event(ev1: Dict[str, Any], ev2: Dict[str, Any], threshold: float = 0.65) -> bool:
    """Sprawdza, czy dwa wydarzenia to ta sama impreza (musi zgadzać się data + podobieństwo tytułu)."""
    if ev1.get("date") != ev2.get("date"):
        return False

    t1 = normalize_title(ev1.get("title", ""))
    t2 = normalize_title(ev2.get("title", ""))

    if not t1 or not t2:
        return False

    # Dokładne dopasowanie po normalizacji
    if t1 == t2 or t1 in t2 or t2 in t1:
        return True

    # Miara podobieństwa Levenshteina / SequenceMatcher
    ratio = SequenceMatcher(None, t1, t2).ratio()
    return ratio >= threshold


def merge_event_records(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """Łączy dwa rekordy, dając priorytet danym o wyższej jakości (tekst z MOK nad ubogim opisem z UM)."""
    merged = dict(secondary)
    merged.update(primary)

    # Zachowaj dłuższy i pełniejszy opis
    desc1 = primary.get("description", "")
    desc2 = secondary.get("description", "")
    merged["description"] = desc1 if len(desc1) >= len(desc2) else desc2

    # Zachowaj konkretną cenę, jeśli jedna ze stron ma tylko placeholder
    p1 = primary.get("price_range", "")
    p2 = secondary.get("price_range", "")
    if p1 and p1 != "Sprawdź bilety":
        merged["price_range"] = p1
    else:
        merged["price_range"] = p2 or p1

    # Preferuj oryginalny plakat instytucji macierzystej
    merged["image_url"] = primary.get("image_url") or secondary.get("image_url")
    return merged


def deduplicate_events(events_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplikuje listę wydarzeń z różnych źródeł."""
    unique_events: List[Dict[str, Any]] = []

    for event in events_list:
        matched = False
        for i, existing in enumerate(unique_events):
            if is_same_event(event, existing):
                # Scal rekordy – zachowaj ten z bogatszą treścią
                unique_events[i] = merge_event_records(event, existing)
                matched = True
                break

        if not matched:
            unique_events.append(event)

    return unique_events