import logging

def compile_venue_rules(place, event):
    rules = {}
    
    def get_val(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    # POZIOM 4: Semantyka kategorii miejsca
    cat = (get_val(place, 'category') or '').lower()
    if cat in ['park', 'pitch', 'plener', 'outdoor']:
        rules['pets'] = {"label": "🐾 Zwierzęta", "val": "Smycz", "desc": "Dozwolone (na smyczy)."}
        rules['cloakroom'] = {"label": "🧥 Szatnia", "val": "Brak", "desc": "Brak (wydarzenie plenerowe)."}
        rules['age_policy'] = {"label": "👶 Wiek", "val": "Brak limitu", "desc": "Brak ograniczeń wiekowych."}
    elif cat in ['nightclub', 'pub', 'bar']:
        rules['age_policy'] = {"label": "🔞 Wiek", "val": "18+", "desc": "Wstęp 18+, możliwa selekcja przy wejściu."}
        rules['restrictions'] = {"label": "🚫 Ograniczenia", "val": "Selekcja", "desc": "Ochrona ma prawo odmówić wstępu."}

    # POZIOM 3: Dostępność dla wózków (OpenStreetMap + Baza Places + Event Fallback)
    wheel = get_val(place, 'wheelchair')
    if wheel is None:
        wheel = get_val(event, 'wheelchair_accessible')
    if wheel in ['yes', True]:
        rules['accessibility'] = {"label": "♿ Dostępność OzN", "val": "Dostępny", "desc": "Obiekt przystosowany architektonicznie (winda/podjazd/parter)."}
    elif wheel == 'limited':
        rules['accessibility'] = {"label": "♿ Dostępność OzN", "val": "Częściowa", "desc": "Obiekt częściowo przystosowany architektonicznie."}
    elif wheel in ['no', False]:
        rules['accessibility'] = {"label": "♿ Dostępność OzN", "val": "Brak", "desc": "Obiekt nieprzystosowany (brak wind, obecne schody)."}

    # Pętla indukcyjna
    loop = get_val(place, 'hearing_loop')
    if loop is None:
        loop = get_val(event, 'hearing_loop')
    if loop in ['yes', True]:
        rules['hearing_loop'] = {"label": "🦻 Pętla indukcyjna", "val": "Dostępna", "desc": "Sala wyposażona w certyfikowaną pętlę indukcyjną (tryb T-coil)."}

    # Kasa biletowa i telefon kontaktowy
    phone = get_val(place, 'box_office_phone') or get_val(place, 'phone') or get_val(event, 'box_office_phone')
    if phone:
        rules['box_office'] = {"label": "📞 Kasa biletowa", "val": str(phone), "desc": f"Informacje o dostępności i rezerwacje: {phone}"}

    # POZIOM 2: Reguły instytucjonalne z bazy obiektów (place['rules'])
    place_rules = get_val(place, 'rules')
    if place_rules and isinstance(place_rules, dict):
        for k, v in place_rules.items():
            rules[k] = v

    # POZIOM 1: Ostrzeżenia sensoryczne i reguły spektaklu (Event Overrides)
    warnings = get_val(event, 'warnings') or []
    if warnings:
        rules['warnings'] = {"label": "⚠️ Ostrzeżenia", "val": ", ".join(warnings), "desc": f"W wydarzeniu wykorzystywane są: {', '.join(warnings)}"}

    an = get_val(event, 'analysis')
    if an:
        ev_rules = get_val(an, 'rules')
        if ev_rules and isinstance(ev_rules, dict):
            for k, v in ev_rules.items():
                rules[k] = v

    return rules
