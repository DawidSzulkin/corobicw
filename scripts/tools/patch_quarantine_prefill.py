import re
from pathlib import Path

server_file = Path("scripts/tools/quarantine_server.py")
if not server_file.exists():
    print("[!] Nie znaleziono scripts/tools/quarantine_server.py")
    exit(1)

code = server_file.read_text(encoding="utf-8")

# Logika wyciągania ulicy z payloadu wydarzenia
clean_street_logic = '''
        # Automatyczne wyciąganie ulicy zebranej przez scraper
        detected_street = ""
        for ev in events_list:
            raw_addr = ev.get("address", "")
            if not raw_addr and "analysis" in ev:
                raw_addr = ev["analysis"].get("address", "")
            
            if raw_addr:
                # Oczyszczanie adresu z nazwy lokalu i miasta
                clean_s = raw_addr
                for strip_word in [venue_name, city_tag.replace("_", " "), "Bielsko-Biała", "Kędzierzyn-Koźle", "Opole"]:
                    clean_s = re.sub(rf"(?i)\\b{re.escape(strip_word)}\\b", "", clean_s)
                clean_s = clean_s.strip(" ,-")
                if any(k in clean_s.lower() for k in ["ul.", "plac", "al.", "aleja", "rynek", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
                    detected_street = clean_s
                    break
'''

# Wstrzyknięcie logiki przed generowaniem wiersza tabeli
if "detected_street" not in code:
    code = re.sub(
        r'(for (?:idx, )?\(?(?:venue_name|venue), (?:city_tag|city)\)?.*?in .*?:)',
        r'\1' + clean_street_logic,
        code
    )
    
    # Wstawienie wyciągniętej ulicy do pola value inputa w Opcji B
    code = re.sub(
        r'(<input[^>]*placeholder=["\']Ulica i numer\.\.\.["\'][^>]*)>',
        r'\1 value="{detected_street}">',
        code
    )
    # Zabezpieczenie dla format-stringów f"..."
    code = re.sub(
        r'placeholder=\\"Ulica i numer\.\.\.\\"',
        r'placeholder=\\"Ulica i numer...\\" value=\\"{detected_street}\\"',
        code
    )

server_file.write_text(code, encoding="utf-8")
print("[OK] quarantine_server.py zaktualizowany. Adresy będą uzupełniane automatycznie.")
