from pathlib import Path

file_path = Path("scripts/tools/quarantine_server.py")
if not file_path.exists():
    print("[!] Brak pliku.")
    exit(1)

code = file_path.read_text(encoding="utf-8")

# 1. Wyłączenie autouzupełniania przeglądarki w polach tekstowych
code = code.replace('name="target_mapping"', 'name="target_mapping" autocomplete="off"')
code = code.replace('name="name"', 'name="name" autocomplete="off"')
code = code.replace('name="street"', 'name="street" autocomplete="off"')

# 2. Naprawa przypisywania ID w bazie SQLite (głębokie szukanie nazwy lokalu)
old_v = 'v = ev.get("venue") or ""'
new_v = 'v = ev.get("venue") or ev.get("analysis", {}).get("ticket_info", {}).get("venue_name") or ""\n                    v = v.strip()'
code = code.replace(old_v, new_v)

file_path.write_text(code, encoding="utf-8")
print("[OK] Kwarantanna załatana: wyłączono autocomplete przeglądarki i naprawiono głębokie zapisywanie obiektów w bazie.")
