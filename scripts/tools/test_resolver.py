import sys
from pathlib import Path
import json
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.domain.pipeline import _calculate_place_similarity, _resolve_place, _load_places_index

def run_unit_tests():
    print("\n" + "="*50)
    print(" TESTY JEDNOSTKOWE POPRAWIONEGO SILNIKA")
    print("="*50)

    test_cases = [
        (
            "Mieszko Minkiewicz - Wszystko Dobrze Opole NCPP - Sala Kameralna",
            "Narodowe Centrum Polskiej Piosenki",
            0.75,
            "Akronim NCPP -> Pełna nazwa"
        ),
        (
            "Katarzyna Piasecka Stand-up Studenckie Centrum Kultury",
            "Studenckie Centrum Kultury",
            0.85,
            "Dokładne dopasowanie tokenów"
        ),
        (
            "Koncert Filharmonia Opolska im. Józefa Elsnera",
            "Filharmonia Opolska",
            0.85,
            "Dopasowanie z pominięciem patrona"
        ),
        (
            "Spektakl Teatr im. Jana Kochanowskiego w Opolu",
            "Teatr Dramatyczny im. Jana Kochanowskiego",
            0.80,
            "Dopasowanie teatru z pominięciem stopwordów i miasta"
        ),
        (
            "Wydarzenie w Opolu Teatr Jana Kochanowskiego",
            "OPO",
            0.00,
            "Brak powiązania ze skrótem OPO (False Positive Check)"
        )
    ]

    passed = 0
    for query, osm_name, min_expected, label in test_cases:
        score = _calculate_place_similarity(query, osm_name, city_tag="opole")
        ok = score >= min_expected if min_expected > 0 else score < 0.40
        status = "[PASS]" if ok else "[FAIL]"
        if ok: passed += 1
        print(f"{status} | Score: {score:.2f} (wymagane: >={min_expected:.2f}) | {label}")

    print(f"\nWynik testów jednostkowych: {passed}/{len(test_cases)} zaliczonych.\n")

def test_opole_resolver():
    print("="*50)
    print(" TEST INTEGRACYJNY NA PLIKU data/opole/places_clean.json ORAZ REGUŁACH YAML")
    print("="*50)

    places = _load_places_index("opole")
    if not places:
        print("[FAIL] Brak pliku data/opole/places_clean.json")
        return

    cfg_path = BASE_DIR / "config" / "opole.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    sample_events = [
        {"title": "Mieszko Minkiewicz", "venue": "Opole NCPP - Sala Kameralna"},
        {"title": "Klimakterium", "venue": "Opole Filharmonia Opolska im. Józefa Elsnera"},
        {"title": "Polska Noc Kabaretowa", "venue": "Opole Amfiteatr Tysiąclecia (Narodowe Centrum Polskiej Piosenki)"},
        {"title": "Stand-up", "venue": "Opole Studenckie Centrum Kultury"},
        {"title": "Spektakl", "venue": "Teatr im. Jana Kochanowskiego w Opolu"}
    ]

    for ev in sample_events:
        matched = _resolve_place(ev, places, cfg)
        matched_name = matched.get("name") if matched else "BRAK DOPASOWANIA"
        print(f"Query: '{ev['venue']}'\n -> Dopasowano: {matched_name}\n")

if __name__ == "__main__":
    run_unit_tests()
    test_opole_resolver()
