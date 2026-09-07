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
        rules['pets'] = {"label": "Zwierzęta", "val": "Smycz", "desc": "Dozwolone (na smyczy).", "is_positive": True}
        rules['cloakroom'] = {"label": "Szatnia", "val": "Brak", "desc": "Brak (wydarzenie plenerowe).", "is_positive": False}
        rules['age_policy'] = {"label": "Wiek", "val": "Brak limitu", "desc": "Brak ograniczeń wiekowych.", "is_positive": True}
    elif cat in ['nightclub', 'pub', 'bar']:
        rules['age_policy'] = {"label": "Wiek", "val": "18+", "desc": "Wstęp 18+, możliwa selekcja przy wejściu.", "is_positive": True}
        rules['restrictions'] = {"label": "Ograniczenia", "val": "Selekcja", "desc": "Ochrona ma prawo odmówić wstępu.", "is_positive": False}

    # POZIOM 3: Dostępność dla wózków (OpenStreetMap + Baza Places + Event Fallback)
    wheel = get_val(place, 'wheelchair')
    if wheel is None:
        wheel = get_val(event, 'wheelchair_accessible')
    if wheel in ['yes', True, 'Tak', 'Dostępny']:
        rules['accessibility'] = {"label": "Dostęp dla wózków", "val": "Tak (winda / podjazd)", "desc": "Obiekt przystosowany architektonicznie.", "is_positive": True}
    elif wheel == 'limited':
        rules['accessibility'] = {"label": "Dostęp dla wózków", "val": "Częściowy", "desc": "Obiekt częściowo przystosowany architektonicznie.", "is_positive": True}
    elif wheel in ['no', False, 'Brak', 'Brak podjazdu']:
        rules['accessibility'] = {"label": "Dostęp dla wózków", "val": "Brak podjazdu", "desc": "Obiekt nieprzystosowany (brak wind, obecne schody).", "is_positive": False}

    # Pętla indukcyjna: Pokazujemy TYLKO gdy jest dostępna LUB gdy to zweryfikowany obiekt sceniczny/teatr
    loop = get_val(place, 'hearing_loop')
    if loop is None:
        loop = get_val(event, 'hearing_loop')
    
    ev_cat = (get_val(event, 'category') or '').lower()
    is_theatre_scene = any(k in ev_cat or k in cat for k in ['teatr', 'opera', 'filharmonia', 'scena'])
    
    if loop in ['yes', True, 'Tak', 'Dostępna', 'Dostępny']:
        rules['hearing_loop'] = {"label": "Pętla indukcyjna", "val": "Dostępna", "desc": "Sala wyposażona w certyfikowaną pętlę indukcyjną.", "is_positive": True}
    elif is_theatre_scene and loop in ['no', False, 'Brak']:
        rules['hearing_loop'] = {"label": "Pętla indukcyjna", "val": "Brak", "desc": "Brak pętli indukcyjnej.", "is_positive": False}

    # Kasa biletowa i telefon kontaktowy (jeden wspólny rekord)
    phone = get_val(place, 'box_office_phone') or get_val(place, 'phone') or get_val(event, 'box_office_phone')
    if phone:
        rules['box_office'] = {"label": "Kasa biletowa", "val": str(phone), "desc": f"Informacje i rezerwacje: {phone}", "is_positive": True, "is_phone": True}

    # Przerwa
    interval = get_val(event, 'interval_str')
    if interval and interval != 'Brak':
        rules['interval'] = {"label": "Przerwa", "val": str(interval), "desc": f"Przerwa: {interval}", "is_positive": True}

    # Ograniczenie wieku
    age_limit = get_val(event, 'age_limit')
    if age_limit and 'age_policy' not in rules:
        rules['age_policy'] = {"label": "Ograniczenie wieku", "val": str(age_limit), "desc": f"Ograniczenie: {age_limit}", "is_positive": True}

    # POZIOM 2: Reguły instytucjonalne z bazy obiektów (place['rules'])
    place_rules = get_val(place, 'rules')
    if place_rules and isinstance(place_rules, dict):
        for k, v in place_rules.items():
            if k not in rules:
                rules[k] = v

    # POZIOM 1: Ostrzeżenia sensoryczne i reguły spektaklu (Event Overrides)
    warnings = get_val(event, 'warnings') or []
    if warnings:
        rules['warnings'] = {"label": "Ostrzeżenia", "val": ", ".join(warnings), "desc": f"W wydarzeniu wykorzystywane są: {', '.join(warnings)}", "is_positive": False}

    an = get_val(event, 'analysis')
    if an:
        ev_rules = get_val(an, 'rules')
        if ev_rules and isinstance(ev_rules, dict):
            for k, v in ev_rules.items():
                rules[k] = v

    return rules