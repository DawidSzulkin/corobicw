import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

GENERIC_NOISE_WORDS = {
    "koncert", "koncerty", "trasa", "tour", "live", "show", "występ", "wystep",
    "bilety", "bilet", "zapraszamy", "nowy", "program", "edycja", "wstęp", "wstep",
    "darmowy", "bezpłatny", "bezplatny", "oficjalny", "legenda", "gwiazda"
}


def normalize_city(city: str) -> str:
    return city.strip().lower() if city else "unknown"


def extract_city_roots(city: str) -> List[str]:
    """Ekstrahuje rdzenie (min. 4 znaki) z nazwy miasta do wycinania odmian gramatycznych."""
    if not city or city == "unknown":
        return []
    words = re.findall(r"\w+", city.lower())
    return [w[:4] for w in words if len(w) >= 4]


def extract_tokens(text: str, city: str = "") -> Tuple[List[str], Set[str]]:
    """Zwraca posortowaną listę wszystkich tokenów oraz zbiór rdzennych słów kluczowych bez szumu."""
    if not text:
        return [], set()

    text = text.lower()
    text = re.sub(r"\b20\d{2}\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    raw_tokens = [t.strip() for t in text.split() if len(t.strip()) > 1]

    city_roots = extract_city_roots(city)

    all_tokens = []
    core_tokens = set()

    for t in raw_tokens:
        # Pomiń tokeny będące odmianami nazwy miasta
        if any(t.startswith(root) for root in city_roots):
            continue
        all_tokens.append(t)
        if t not in GENERIC_NOISE_WORDS:
            core_tokens.add(t)

    return sorted(all_tokens), core_tokens


def extract_date(event: Dict[str, Any]) -> str:
    date_val = str(event.get("date_start") or event.get("date") or "").strip()
    return date_val[:10]


def is_event_match(
    t1_tokens: List[str],
    t1_core: Set[str],
    t2_tokens: List[str],
    t2_core: Set[str],
    threshold: float = 0.60,
) -> bool:
    if not t1_tokens or not t2_tokens:
        return False

    s1 = " ".join(t1_tokens)
    s2 = " ".join(t2_tokens)

    if s1 == s2:
        return True

    # 1. Klasyczne podobieństwo sekwencyjne
    if SequenceMatcher(None, s1, s2).ratio() >= threshold:
        return True

    # 2. Współczynnik Dice'a na pełnych tokenach
    set1, set2 = set(t1_tokens), set(t2_tokens)
    intersection = set1.intersection(set2)
    dice_ratio = (2.0 * len(intersection)) / (len(set1) + len(set2))
    if dice_ratio >= threshold:
        return True

    # 3. Współczynnik Szymkiewicza-Simpsona (Overlap) na rdzennych słowach kluczowych
    if t1_core and t2_core:
        core_intersection = t1_core.intersection(t2_core)
        overlap_ratio = len(core_intersection) / min(len(t1_core), len(t2_core))
        if overlap_ratio >= 0.60:
            return True

    return False


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

        if filter_past_events and date and date < today_str:
            continue

        valid_events_count += 1

        if city == "unknown" or not date:
            unbucketed.append(event)
            continue

        tokens, core_tokens = extract_tokens(event.get("title", ""), city=city)
        event["_tokens"] = tokens
        event["_core_tokens"] = core_tokens
        buckets[(city, date)].append(event)

    logging.info("Wydarzenia po odfiltrowaniu archiwalnych: %d (z %d początkowych)", valid_events_count, len(events_list))

    unique_events: List[Dict[str, Any]] = []

    for (city, date), cluster in buckets.items():
        cluster_unique: List[Dict[str, Any]] = []
        for event in cluster:
            matched = False
            for i, existing in enumerate(cluster_unique):
                if is_event_match(
                    event["_tokens"],
                    event["_core_tokens"],
                    existing["_tokens"],
                    existing["_core_tokens"],
                    threshold=similarity_threshold,
                ):
                    cluster_unique[i] = merge_event_records(event, existing)
                    matched = True
                    break
            if not matched:
                cluster_unique.append(event)

        unique_events.extend(cluster_unique)

    unique_events.extend(unbucketed)

    for event in unique_events:
        event.pop("_tokens", None)
        event.pop("_core_tokens", None)

    return unique_events


def main():
    parser = argparse.ArgumentParser(description="Deduplikator wydarzeń portalu corobicw.pl")
    parser.add_argument("--input", "-i", default="raw_events.json", help="Wejściowy plik JSON")
    parser.add_argument("--output", "-o", default="events_clean.json", help="Wyjściowy plik JSON")
    parser.add_argument("--threshold", "-t", type=float, default=0.60, help="Próg podobieństwa")
    parser.add_argument("--keep-past", action="store_true", help="Wyłącza usuwanie wydarzeń z przeszłości")

    args = parser.parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        logging.error("Brak pliku: %s", input_path)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    cleaned = process_events(raw_data, similarity_threshold=args.threshold, filter_past_events=not args.keep_past)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    logging.info("Zapisano %d zdeduplikowanych wydarzeń do %s", len(cleaned), output_path)


if __name__ == "__main__":
    main()
