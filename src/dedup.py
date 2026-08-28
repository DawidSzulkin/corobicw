import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def normalize_city(city: str) -> str:
    return city.strip().lower() if city else "unknown"


def normalize_title(text: str, city: str = "") -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\b20\d{2}\b", "", text)  # usuwa lata (np. 2026)
    
    # Usuwanie nazwy miasta z tytułu (zapobiega spadkowi ratio przy inwersji słów)
    if city and city != "unknown":
        text = re.sub(rf"\b{re.escape(city.lower())}\b", "", text)
        
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 1]
    
    # Sortowanie alfabetyczne tokenów
    return " ".join(sorted(tokens))


def extract_date(event: Dict[str, Any]) -> str:
    date_val = str(event.get("date_start") or event.get("date") or "").strip()
    return date_val[:10]


def is_title_similar(t1: str, t2: str, threshold: float = 0.60) -> bool:
    if not t1 or not t2:
        return False
    if t1 == t2:
        return True

    # 1. SequenceMatcher
    if SequenceMatcher(None, t1, t2).ratio() >= threshold:
        return True

    # 2. Dice Coefficient (miara nakładania zbiorów)
    set1, set2 = set(t1.split()), set(t2.split())
    if not set1 or not set2:
        return False

    intersection = set1.intersection(set2)
    dice_ratio = (2.0 * len(intersection)) / (len(set1) + len(set2))
    return dice_ratio >= threshold


def clean_field_value(value: Any, blacklist_tokens: List[str]) -> str:
    if not value:
        return ""
    val_str = str(value).strip()
    for token in blacklist_tokens:
        if token.lower() in val_str.lower():
            return ""
    return val_str


def merge_event_records(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(secondary)
    for k, v in primary.items():
        if v is not None and v != "":
            merged[k] = v

    desc1 = str(primary.get("description") or primary.get("analysis", {}).get("full_description", "")).strip()
    desc2 = str(secondary.get("description") or secondary.get("analysis", {}).get("full_description", "")).strip()
    merged["description"] = desc1 if len(desc1) >= len(desc2) else desc2

    p1 = clean_field_value(
        primary.get("price_range") or primary.get("analysis", {}).get("ticket_info", {}).get("price_range"),
        ["sprawdź", "sprawdz", "n/a", "brak", "brak danych"],
    )
    p2 = clean_field_value(
        secondary.get("price_range") or secondary.get("analysis", {}).get("ticket_info", {}).get("price_range"),
        ["sprawdź", "sprawdz", "n/a", "brak", "brak danych"],
    )
    merged["price_range"] = p1 or p2

    img1 = clean_field_value(primary.get("image_url"), ["unsplash.com", "placeholder", "default_event"])
    img2 = clean_field_value(secondary.get("image_url"), ["unsplash.com", "placeholder", "default_event"])
    merged["image_url"] = img1 or img2

    merged["city"] = primary.get("city") or secondary.get("city")
    merged["date_start"] = extract_date(primary) or extract_date(secondary)

    return merged


def process_events(
    events_list: List[Dict[str, Any]],
    similarity_threshold: float = 0.60,
    filter_past_events: bool = True,
) -> List[Dict[str, Any]]:
    today_str = datetime.now().strftime("%Y-%m-%d")
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    unbucketed: List[Dict[str, Any]] = []
    valid_events_count = 0

    for event in events_list:
        city = normalize_city(event.get("city", ""))
        date = extract_date(event)

        # Odrzucanie starych wydarzeń
        if filter_past_events and date and date < today_str:
            continue

        valid_events_count += 1

        if city == "unknown" or not date:
            unbucketed.append(event)
            continue

        event["_norm_title"] = normalize_title(event.get("title", ""), city=city)
        buckets[(city, date)].append(event)

    logging.info("Wydarzenia po odfiltrowaniu archiwalnych: %d (z %d początkowych)", valid_events_count, len(events_list))

    unique_events: List[Dict[str, Any]] = []

    for (city, date), cluster in buckets.items():
        cluster_unique: List[Dict[str, Any]] = []
        for event in cluster:
            matched = False
            for i, existing in enumerate(cluster_unique):
                if is_title_similar(event["_norm_title"], existing["_norm_title"], threshold=similarity_threshold):
                    cluster_unique[i] = merge_event_records(event, existing)
                    matched = True
                    break
            if not matched:
                cluster_unique.append(event)

        unique_events.extend(cluster_unique)

    unique_events.extend(unbucketed)

    # Sprzątanie pomocniczych kluczy
    for event in unique_events:
        event.pop("_norm_title", None)

    return unique_events


def main():
    parser = argparse.ArgumentParser(description="Deduplikator wydarzeń portalu corobicw.pl")
    parser.add_argument("--input", "-i", default="raw_events.json", help="Wejściowy plik JSON")
    parser.add_argument("--output", "-o", default="events_clean.json", help="Wyjściowy plik JSON")
    parser.add_argument("--threshold", "-t", type=float, default=0.60, help="Próg podobieństwa (domyślnie 0.60)")
    parser.add_argument("--keep-past", action="store_true", help="Wyłącza usuwanie wydarzeń z przeszłości")

    args = parser.parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        logging.error("Brak pliku wejściowego: %s", input_path)
        sys.exit(1)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            if not isinstance(raw_data, list):
                raise ValueError("JSON musi zawierać listę obiektów.")
    except Exception as e:
        logging.error("Błąd ładowania JSON: %s", e)
        sys.exit(1)

    cleaned = process_events(
        raw_data,
        similarity_threshold=args.threshold,
        filter_past_events=not args.keep_past,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    logging.info("Zapisano %d zdeduplikowanych wydarzeń do %s", len(cleaned), output_path)


if __name__ == "__main__":
    main()