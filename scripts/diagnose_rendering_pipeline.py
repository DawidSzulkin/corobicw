import sys
import os
from pathlib import Path

# Zapewnienie poprawnej ścieżki importu dla pakietu src
ROOT_DIR = Path(__file__).resolve().parent.parent if "scripts" in str(Path(__file__)) else Path(".").resolve()
sys.path.insert(0, str(ROOT_DIR))

import sqlite3
import json
import re
from jinja2 import Environment, FileSystemLoader

print("===================================================================")
print(" 1. SCHEMAT BAZY DANYCH I STRUKTURA REKORDU BARTOSZA GAJDY")
print("===================================================================")

db_paths = list(ROOT_DIR.glob("**/*.db")) + list(ROOT_DIR.glob("**/*.sqlite"))
db_paths = [p for p in db_paths if "backup" not in p.name]

raw_row_dict = {}
target_db = None
target_table = None

for db in db_paths:
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        
        for tbl in tables:
            cur.execute(f"PRAGMA table_info({tbl})")
            cols = [c[1] for c in cur.fetchall()]
            
            cur.execute(f"SELECT * FROM {tbl}")
            for r in cur.fetchall():
                d = dict(r)
                row_str = json.dumps(d, default=str, ensure_ascii=False)
                if "Gajda" in row_str or "PO LECIE" in row_str:
                    raw_row_dict = d
                    target_db = db
                    target_table = tbl
                    print(f"[ZNALEZIONO REKORD] Baza: {db.name} | Tabela: {tbl}")
                    print(f"Kolumny tabeli: {cols}\n")
                    for k, v in d.items():
                        v_str = str(v)
                        preview = v_str[:120] + f"... (długość: {len(v_str)})" if len(v_str) > 120 else v_str
                        print(f"  - {k}: {preview}")
                    break
            if raw_row_dict:
                break
        conn.close()
        if raw_row_dict:
            break
    except Exception as e:
        print(f"Błąd czytania {db}: {e}")

if not raw_row_dict:
    print("[BŁĄD] Nie znaleziono wpisu o Gajdzie w żadnej bazie SQLite!")

print("\n===================================================================")
print(" 2. FRAGMENT SZABLONU templates/event_page.html (SEKCJA OPISU)")
print("===================================================================")
tpl_file = ROOT_DIR / "templates" / "event_page.html"
if tpl_file.exists():
    lines = tpl_file.read_text(encoding="utf-8").splitlines()
    for idx, l in enumerate(lines, 1):
        if any(k in l for k in ["event-desc", "description", "formatted_description", "full_description", "analysis"]):
            print(f"Linia {idx:3d}: {l}")

print("\n===================================================================")
print(" 3. FRAGMENT src/infrastructure/renderer.py (PĘTLA WYDARZEŃ)")
print("===================================================================")
rend_file = ROOT_DIR / "src" / "infrastructure" / "renderer.py"
if rend_file.exists():
    r_lines = rend_file.read_text(encoding="utf-8").splitlines()
    for idx, l in enumerate(r_lines, 1):
        if "event_template.render(" in l:
            start = max(0, idx - 8)
            end = min(len(r_lines), idx + 12)
            for j in range(start, end):
                print(f"Linia {j+1:3d}: {r_lines[j]}")
            break

print("\n===================================================================")
print(" 4. DRY-RUN: EMULACJA RENDEROWANIA DLA BARTOSZA GAJDY")
print("===================================================================")
try:
    from src.infrastructure.renderer import HTMLRenderer
    
    # Inicjalizacja rzeczywistego renderera
    renderer = HTMLRenderer(template_dir=str(ROOT_DIR / "templates"), output_dir=str(ROOT_DIR / "public"))
    
    # Rekonstrukcja obiektu w taki sposób, w jaki renderer go otrzymuje w pipeline
    class MockAnalysis:
        def __init__(self, raw):
            if isinstance(raw, dict):
                for k, v in raw.items(): setattr(self, k, v)
            elif isinstance(raw, str):
                try:
                    data = json.loads(raw)
                    for k, v in data.items(): setattr(self, k, v)
                except Exception:
                    self.full_description = raw

    class MockEvent:
        def __init__(self, row):
            for k, v in row.items():
                setattr(self, k, v)
            if "analysis" in row and row["analysis"]:
                self.analysis = MockAnalysis(row["analysis"])
            elif not hasattr(self, "analysis"):
                self.analysis = None

    ev_obj = MockEvent(raw_row_dict)
    
    # Test bezpośredniej funkcji procesora z renderer.py
    import src.infrastructure.renderer as r_mod
    if hasattr(r_mod, "_process_event_description_to_html"):
        extracted = r_mod._process_event_description_to_html(ev_obj)
        print(f"[TEST PROCESORA] Długość wygenerowanego HTML: {len(extracted)} znaków")
        print(f"[TEST PROCESORA] Liczba znaczników <p>: {extracted.count('<p>')}")
        print(f"[TEST PROCESORA] Czy 'więcej informacji' obecne: {'TAK (BŁĄD)' if 'więcej informacji' in extracted.lower() else 'NIE (CZYSTO)'}")
        print("\nFragment wygenerowanego HTML:\n" + extracted[:400] + ("..." if len(extracted) > 400 else ""))
    else:
        print("[OSTRZEŻENIE] Brak funkcji _process_event_description_to_html w module renderer!")

except Exception as e:
    print(f"[WYJĄTEK PODCZAS DRY-RUN]: {e}")
    import traceback
    traceback.print_exc()

print("\n===================================================================")
print("                   AUDYT ZAKOŃCZONY                                ")
print("===================================================================")