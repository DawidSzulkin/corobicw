import re

def extract_rules_from_text(text: str) -> dict:
    if not text:
        return {}

    clean_text = re.sub(r'<[^>]+>', ' ', text).lower()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    rules = {}

    # 1. Wiek i wstęp
    age_patterns = [
        r"\bod\s+lat\s+(?:[1-9]|1[0-8])\b",
        r"\bod\s+(?:[1-9]|1[0-8])\s+(?:roku\s+życia|r\.?\s*ż\.?)\b",
        r"\b(?:wstęp|wejście|dla|widz[a-ząćęłńóśźż]*|osób|osoby|wiek[u]?|kategori[a-z]*|przeznaczon[eya-z]*)\b[^.\n]{0,35}?\b(?:od\s+)?(?:[1-9]|1[0-8])\s+lat\b",
        r"\b(?:minimalny\s+wiek|kategoria\s+wiekowa|wiek\s+uczestnik[a-ząćęłńóśźż]*)\b[^.\n]{0,35}?\b(?:od\s+)?(?:[1-9]|1[0-8])\s+lat\b",
        r"\b(?:1[268]|18)\s*\+(?!\w)",
        r"\b(?:tylko|wyłącznie)\s+dla\s+(?:(?:widzów|osób|gości|publiczności|uczestników)\s+)?(?:dorosłych|pełnoletnich)\b",
        r"\b(?:tylko|wyłącznie)\s+dla\s+(?:dorosłych|pełnoletnich)\s+(?:widzów|osób|gości|uczestników)?\b",
        r"\bza\s+zgodą\s+(?:opiekuna|rodzica|rodziców|opiekunów)\b",
        r"\bbez\s+ograniczeń\s+wiekowych\b",
        r"\b(?:dla\s+dzieci|dzieci|osób)\s+(?:do|od|poniżej|powyżej)\s+(?:lat|roku\s+życia)\s+(?:[1-9]|1[0-8])\b",
        r"\b(?:dla\s+dzieci|dzieci|osób)\s+(?:do|od|poniżej|powyżej)\s+(?:[1-9]|1[0-8])\s+(?:lat|roku\s+życia)\b"
    ]
    if any(re.search(pat, clean_text) for pat in age_patterns):
        # Negacja stażu i godzin
        if not re.search(r"\bod\s+(?:[1-9]|1[0-8])\s+lat\s+(?:w\s+|doświadczenia|tradycji|działalności|na\s+|pracy|istnienia|funkcjonowania|historii|praktyki|obecności|sukcesów|tworzymy|gramy|działamy|prowadzimy|organizujemy|kształcimy|zajmujemy)", clean_text):
            rules["age_policy"] = {"label": "🔞 Wiek i wstęp", "val": "Zasady wiekowe"}

    # 2. Czas trwania
    if re.search(
        r"(\bczas\s+trwania\b[^;\n]{0,45}?\b\d+(?:[.,]\d+)?\s*(?:min(?:ut[y]?)?|godz(?:in[ay]?)?|h)\b)"
        r"|(\b(?:trwa|potrwa|przewidywany\s+czas(?:\s+trwania)?)\s+(?:ok(?:\.|oło)?\s*)?\d+(?:[.,]\d+)?\s*(?:min(?:ut[y]?)?|godz(?:in[ay]?)?|h)\b)"
        r"|(\b\d+(?:[.,]\d+)?\s*(?:min(?:ut[y]?)?|godz(?:in[ay]?)?|h)\s*(?:bez\s+przerw[ay]?|bez\s+antraktu|z\s+przerwą|z\s+antraktem)\b)",
        clean_text
    ):
        rules["duration"] = {"label": "⏱️ Czas trwania", "val": "Określony"}

    # 3. Ostrzeżenia sceniczne
    if re.search(
        r"(\bstroboskop[a-ząćęłńóśźż]*\b)"
        r"|(\b(?:światła|efekty|błyski)\s+stroboskopowe\b)"
        r"|(\befekt[a-ząćęłńóśźż]*\s+dymn[a-ząćęłńóśźż]*\b)"
        r"|(\b(?:dym|dymy)\s+(?:sceniczn[a-z]*|sztuczn[a-z]*)\b)"
        r"|(\bsztuczn[a-z]*\s+dym\b)"
        r"|(\bdym(?:u|em)?\s+sceniczn[a-ząćęłńóśźż]*\b)"
        r"|(\bepileps[a-ząćęłńóśźż]*\b)"
        r"|(\b(?:hałas|hałasem|głośny|bardzo\s+głośny)\s+dźwięk\b)"
        r"|(\b(?:ochrona|ochronniki|zatyczki)\s+(?:słuchu|do\s+uszu)\b)"
        r"|(\befekt[yów]*\s+pirotechniczn[a-z]*\b)",
        clean_text
    ):
        rules["health_warnings"] = {"label": "⚡ Efekty sceniczne", "val": "Stroboskopy / Dym"}

    # 4. Spóźnienia
    if re.search(
        r"(\b(?:wejści[ae]|wstęp[u]?|wpuszczan[iy]|wpuszczanie)\s+po\s+rozpoczęciu\b)"
        r"|(\bpo\s+rozpoczęciu\s+(?:spektaklu|koncertu|wydarzenia|seansu|imprezy|przedstawienia|seansu)\b[^.\n]{0,40}?\b(?:jest\s+)?(?:niemożliwe|wstrzyman[ey]|zamknięt[ey]|brak)\b)"
        r"|(\b(?:brak|nie\s+ma)\s+możliwości\s+wejścia\s+po\b)"
        r"|(\bpo\s+trzecim\s+dzwonku\b)"
        r"|(\b(?:osoby\s+spóźnione|spóźnieni(?:\s+widzowie|\s+goście)?|spóźnialscy)\b)"
        r"|(\b(?:dopiero|wpuszczani)\s+(?:w\s+trakcie\s+|na\s+)?antrakt[u]?\b)"
        r"|(\b(?:drzwi|wejście|wejścia|bramy)\b[^.\n]{0,40}?\b(?:zamknięte|zamykane|zamyka)\b[^.\n]{0,30}?\bpunktualnie\b)"
        r"|(\b(?:zamyka|zamykane|zamknięte|zamykamy)\s+(?:wejście|drzwi|bramy)\b[^.\n]{0,40}?\bpunktualnie\b)"
        r"|(\bpunktualnie\b[^.\n]{0,30}?\bzamykamy\s+(?:drzwi|wejście)\b)",
        clean_text
    ):
        rules["latecomers"] = {"label": "🔔 Spóźnienia", "val": "Ograniczenia wejścia"}

    # 5. Bagaż i Depozyt
    if re.search(
        r"(\b(?:bagaż|bagaże|bagaży|bagażem|toreb|plecaków|walizek|plecak[a-ząćęłńóśźż]*|toreb[a-ząćęłńóśźż]*)\b[^.\n]{0,60}?\bformat(?:u|em)?\s*a4\b)"
        r"|(\bformat(?:u|em)?\s*a4\b[^.\n]{0,60}?\b(?:bagaż|bagaże|toreb|plecaków|walizek)\b)"
        r"|(\b(?:zakaz|nie\s+można|niewnoszenie|zakazuje\s+się|nie\s+wolno|zabrania\s+się)\b[^.\n]{0,30}?\b(?:wnoszenia|wnosić)?\b[^.\n]{0,30}?\b(?:dużych\s+|gabarytowych\s+)?(?:plecaków|toreb|bagaż[au]|walizek)\b)"
        r"|(\b(?:zostawić|zdać|oddać)\s+(?:bagaż|rzeczy|walizki|torby|plecaki|kurtki)?\s*(?:do|w|na)\s+depozy[ct][a-ząćęłńóśźż]*\b)"
        r"|(\bdepozy[ct](?:owy|owego|owej|owych|zie|u|em)?\s+festiwalow[a-z]*\b)"
        r"|(\bdepozyt\s+(?:bagażowy|dla\s+widzów|obowiązkowy)\b)"
        r"|(\brzeczy\s+gabarytowe\b[^.\n]{0,40}?\bdepozy[ct][a-ząćęłńóśźż]*\b)",
        clean_text
    ):
        rules["bag_restrictions"] = {"label": "🎒 Bagaż i depozyt", "val": "Max. format A4"}

    # 6. Rejestracja foto/video
    if re.search(
        r"(\b(?:zakaz|nie\s+wolno|kategoryczny\s+zakaz|całkowity\s+zakaz|zabrania\s+się|zakazuje\s+się)\b[^.\n]{0,30}?\b(?:wnoszenia|wnosić)?\b[^.\n]{0,45}?\b(?:fotografowania|nagrywania|filmowania|rejestracji|aparat[oóywa-z]*|kamer[a-z]*|statyw[oóywa-z]*|lustrzanek|sprzętu\s+foto)\b)"
        r"|(\b(?:aparaty|aparatów|sprzęt[u]?)\b[^.\n]{0,35}?\b(?:z\s+wymienną|z\s+profesjonalną)\s+optyką\b)"
        r"|(\b(?:nagrywanie|fotografowanie|filmowanie|rejestracja|rejestrowanie)\b[^.\n]{0,80}?\b(?:surowo\s+|kategorycznie\s+|bezwzględnie\s+)?(?:wzbronion[a-z]*|zabronion[a-z]*|zakazan[a-z]*|niedozwolon[a-z]*|zakaz)\b)"
        r"|(\brejestracj[a-z]*\s+(?:foto|audio|video|wideo|audio-video|audio-wideo)\b[^.\n]{0,60}?\b(?:zabronion[a-z]*|zakazan[a-z]*|niedozwolon[a-z]*|wzbronion[a-z]*)\b)",
        clean_text
    ):
        rules["photo_policy"] = {"label": "📷 Rejestracja foto/video", "val": "Zakaz foto pro"}

    # 7. Personalizacja i dokumenty
    if re.search(
        r"(\bbilet[a-ząćęłńóśźż]*\s+(?:są\s+|będą\s+)?imienn[a-ząćęłńóśźż]*\b)"
        r"|(\b(?:dokument[a-ząćęłńóśźż]*|dowód|dowod[a-ząćęłńóśźż]*)\s+(?:tożsamości|osobist[a-ząćęłńóśźż]*)\b[^.\n]{0,70}?\b(?:wstęp[a-ząćęłńóśźż]*|wejści[a-ząćęłńóśźż]*|bramk[a-ząćęłńóśźż]*|kontrol[a-ząćęłńóśźż]*|okazan[a-ząćęłńóśźż]*|weryfikacj[a-ząćęłńóśźż]*|bilet[a-ząćęłńóśźż]*|skanowan[a-ząćęłńóśźż]*|potwierdzen[a-ząćęłńóśźż]*|zgodnoś[a-ząćęłńóśźż]*|wymagan[a-ząćęłńóśźż]*|sprawdzan[a-ząćęłńóśźż]*|niezbędn[a-ząćęłńóśźż]*)\b)"
        r"|(\b(?:wstęp[a-ząćęłńóśźż]*|wejści[a-ząćęłńóśźż]*|bramk[a-ząćęłńóśźż]*|kontrol[a-ząćęłńóśźż]*|okazan[a-ząćęłńóśźż]*|weryfikacj[a-ząćęłńóśźż]*|bilet[a-ząćęłńóśźż]*|skanowan[a-ząćęłńóśźż]*|potwierdzen[a-ząćęłńóśźż]*|zgodnoś[a-ząćęłńóśźż]*|wymagan[a-ząćęłńóśźż]*|sprawdzan[a-ząćęłńóśźż]*|niezbędn[a-ząćęłńóśźż]*)\b[^.\n]{0,70}?\b(?:dokument[a-ząćęłńóśźż]*|dowód|dowod[a-ząćęłńóśźż]*)\s+(?:tożsamości|osobist[a-ząćęłńóśźż]*)\b)"
        r"|(\b(?:weryfikacja|zgodność)\s+danych\s+(?:z\s+dokumentem|z\s+dowodem|na\s+bilecie)\b)",
        clean_text
    ):
        rules["ticket_nominal"] = {"label": "🪪 Personalizacja", "val": "Wymagany dokument"}

    # 8. Alkohol i restrykcje napojów
    alc_ban = re.search(
        r"(\b(?:zakaz|zakazuje\s+się|nie\s+wolno|nie\s+można|niewnoszenie|niewnoszenia|zabrania\s+się|zakazane)\b[^.\n]{0,60}?\b(?:alkoholu|napojów|butelek|szkła|płynów|puszek|szklanych\s+opakowań)\b)"
        r"|(\b(?:wnoszeni[ae]|wnosić)\s+(?:własn[eych]+\s+)?(?:alkoholu|napojów|butelek|szkła|płynów|szklanych\s+opakowań)\b)",
        clean_text
    )
    alc_free = re.search(r"(\bbezalkoholow[a-ząćęłńóśźż]+\b)", clean_text)
    alc_fest = re.search(
        r"(\bstref[a-y]\s+(?:z\s+)?(?:piwem|piwn[a-y]|alkohol[a-z]*|win[a-z]*|cydr[a-z]*)\b)"
        r"|(\bbar\s+piwny\b)"
        r"|(\bpiw[a-ząćęłńóśźż]*\s+(?:z\s+kija|rzemieślnicz[a-z]*|kraftow[a-z]*|lan[a-z]*)\b)"
        r"|(\bdegustacj[a-z]\s+win[a-z]*\b)"
        r"|(\bfestiwal[u]?\s+piw[a-y]?\b)"
        r"|(\boktoberfest\b)",
        clean_text
    )

    if alc_ban or alc_free or alc_fest:
        rules["alcohol_policy"] = {"label": "🍺 Alkohol i napoje", "val": "Zasady napojów"}

    return rules

