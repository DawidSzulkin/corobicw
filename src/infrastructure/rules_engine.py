import logging

def compile_venue_rules(place, event):
    rules = {}
    
    # Pomocnik do bezpiecznego odczytu pól z dict lub obiektu
    def get_val(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    # 1. POZIOM 4: Semantyka kategorii miejsca
    cat = (get_val(place, 'category') or '').lower()
    if cat in ['park', 'pitch', 'plener', 'outdoor']:
        rules['pets'] = {"label": "🐕 Zwierzęta", "val": "Smycz", "desc": "Dozwolone (na smyczy)."}
        rules['cloakroom'] = {"label": "🧥 Szatnia", "val": "Brak", "desc": "Brak (wydarzenie plenerowe)."}
        rules['age_policy'] = {"label": "👶 Wiek", "val": "Brak limitu", "desc": "Brak ograniczeń wiekowych."}
    elif cat in ['nightclub', 'pub', 'bar']:
        rules['age_policy'] = {"label": "🔞 Wiek", "val": "18+", "desc": "Wstęp 18+, możliwa selekcja przy wejściu."}
        rules['restrictions'] = {"label": "🚫 Ograniczenia", "val": "Selekcja", "desc": "Ochrona ma prawo odmówić wstępu."}

    # 2. POZIOM 3: Dane OpenStreetMap
    wheel = get_val(place, 'wheelchair')
    if wheel == 'yes':
        rules['accessibility'] = {"label": "♿ Dostępność OzN", "val": "Dostępny", "desc": "Obiekt w pełni przystosowany (winda/podjazd)."}
    elif wheel == 'limited':
        rules['accessibility'] = {"label": "♿ Dostępność OzN", "val": "Częściowa", "desc": "Obiekt częściowo przystosowany."}
    elif wheel == 'no':
        rules['accessibility'] = {"label": "♿ Dostępność OzN", "val": "Brak", "desc": "Brak udogodnień dla wózków."}

    # 3. POZIOM 2: Konfiguracja YAML (Tier 1 Venues)
    place_rules = get_val(place, 'rules')
    if place_rules and isinstance(place_rules, dict):
        for k, v in place_rules.items():
            rules[k] = v

    # 4. POZIOM 1: Wyjątki w payloadzie wydarzenia (Normalizator / Scraper)
    an = get_val(event, 'analysis')
    if an:
        ev_rules = get_val(an, 'rules')
        if ev_rules and isinstance(ev_rules, dict):
            for k, v in ev_rules.items():
                rules[k] = v

    return rules