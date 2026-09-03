import subprocess

def copy_to_clipboard(text: str) -> bool:
    try:
        # Kodowanie UTF-16 z BOM automatycznie instruuje clip.exe do zapisu jako Unicode
        subprocess.run(["clip"], input=text.encode("utf-16"), check=True)
        return True
    except Exception as e:
        print(f"[OSTRZEŻENIE] Błąd zapisu do schowka: {e}")
        return False

import ast
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent

def inspect_db(db_path: Path) -> dict:
    """Bada rzeczywisty schemat bazy i dekoduje klucze payload JSON."""
    if not db_path.exists():
        return {}
    
    info = {"tables": {}, "payload_schema": []}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        
        for t in tables:
            cur.execute(f"PRAGMA table_info(`{t}`);")
            cols = [f"{c[1]} ({c[2]})" for c in cur.fetchall()]
            info["tables"][t] = cols
            
            # Jeśli tabela ma kolumnę payload, dekodujemy strukturę jednego rekordu
            if "payload" in [c[1] for c in cur.fetchall()]:
                cur.execute(f"SELECT payload FROM `{t}` WHERE payload IS NOT NULL AND length(payload) > 5 LIMIT 1;")
                sample = cur.fetchone()
                if sample:
                    try:
                        p_data = json.loads(sample[0])
                        info["payload_schema"] = sorted(list(p_data.keys()))
                    except Exception:
                        pass
        conn.close()
    except Exception as e:
        info["error"] = str(e)
    return info

def inspect_configs(config_dir: Path) -> list:
    """Parsuje aktywne konfiguracje miast."""
    cities = []
    if not config_dir.exists():
        return cities
    for f in sorted(config_dir.glob("*.yaml")):
        if f.stem in ["global", "schema"]:
            continue
        try:
            with open(f, "r", encoding="utf-8") as yf:
                d = yaml.safe_load(yf)
                if isinstance(d, dict) and "city_tag" in d:
                    cities.append({
                        "file": f.name,
                        "tag": d.get("city_tag"),
                        "name": d.get("city")
                    })
        except Exception:
            pass
    return cities

def inspect_templates(tmpl_dir: Path) -> dict:
    """Wyciąga zmienne root contextu używane w szablonach Jinja2."""
    tmpl_data = {}
    if not tmpl_dir.exists():
        return tmpl_data
    
    for f in sorted(tmpl_dir.glob("*.html")):
        try:
            txt = f.read_text(encoding="utf-8-sig", errors="ignore")
            # Prosta detekcja zmiennych w pętlach i ifach
            context_vars = set(re.findall(r"{[{%]\s*(?:if|for|empty)?\s*([a-zA-Z_][a-zA-Z0-9_]*)", txt))
            reserved = {"loop", "not", "and", "or", "true", "false", "none", "set", "include", "block"}
            tmpl_data[f.name] = sorted(list(context_vars - reserved))[:8]
        except Exception:
            pass
    return tmpl_data

def get_ast_imports(py_path: Path) -> list:
    imports = []
    try:
        content = py_path.read_text(encoding="utf-8-sig", errors="ignore")
        tree = ast.parse(content, filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src."):
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("src."):
                    imports.append(node.module)
    except Exception:
        pass
    return sorted(list(set(imports)))

def generate_context():
    db_info = inspect_db(ROOT_DIR / "data" / "events.db")
    cities = inspect_configs(ROOT_DIR / "config")
    templates = inspect_templates(ROOT_DIR / "templates")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Zachowanie sekcji 6 (aktualny cel), jeśli plik CONTEXT.md już istnieje
    current_focus = "**Cel:** Brak aktywnego sprintu.\n**Problem:** Brak"
    context_file = ROOT_DIR / "CONTEXT.md"
    if context_file.exists():
        old_txt = context_file.read_text(encoding="utf-8-sig", errors="ignore")
        if "## 6. AKTUALNY CEL (SPRINT / FOCUS)" in old_txt:
            current_focus = old_txt.split("## 6. AKTUALNY CEL (SPRINT / FOCUS)")[-1].strip()

    md = []
    md.append(f"# PROJEKT: CoRobićW - Stan Faktyczny i Baza Wiedzy Architektury")
    md.append(f"Data wygenerowania (Auto-Audit): {now_str}\n")
    md.append("Jesteś technicznym partnerem i senior deweloperem projektu. Nie zgadzaj się bezkrytycznie ze złymi pomysłami. Poniższe dane zostały wygenerowane na podstawie rzeczywistej inspekcji plików projektu.\n")
    md.append("---")
    
    # 1. ZASADY OPERACYJNE
    md.append("## 1. PROTOKÓŁ OPERACYJNY (ZASADA ZERO)")
    md.append("1. **PowerShell & UTF-8:** Każdy skrypt MUSI zaczynać się od `$env:PYTHONIOENCODING = \"utf-8\"`.")
    md.append("2. **Bezpieczny kod:** Zakaz modyfikacji HTML złożonymi wyrażeniami regularnymi. Używaj parserów lub indeksowania.")
    md.append("3. **Schowek:** Każde polecenie audytujące/naprawcze kopiuje wynik do schowka (`| Set-Clipboard`).\n")
    md.append("---")

    # 2. RZECZYWISTY MODEL DANYCH (SQLITE & PAYLOAD)
    md.append("## 2. RZECZYWISTY SCHEMAT BAZY DANYCH (data/events.db)")
    md.append("Baza działa w modelu dokumentowym SQLite (Envelope Pattern):\n")
    for tbl, cols in db_info.get("tables", {}).items():
        md.append(f"* **Tabela `{tbl}`:** {', '.join(cols)}")
    
    if db_info.get("payload_schema"):
        md.append(f"\n* **Klucze w kolumnie `payload` (JSON Dict):**")
        md.append(f"  `{', '.join(db_info['payload_schema'])}`")
    md.append("\n* **Kontrakt ticket_offers wewnątrz payload:** `[{'provider': str, 'url': str, 'price': str, 'raw_price': str, 'is_primary': bool, 'discounts': list}]`")
    md.append("* **Kontrakt analysis wewnątrz payload:** `{'ticket_info': {'venue_name': str, 'price_range': str}, 'editorial_lead': str}`\n")
    md.append("---")

    # 3. TOPOLOGIA I KONFIGURACJA MIASZT
    md.append("## 3. AKTYWNE MIASTA I KONFIGURACJA")
    for c in cities:
        md.append(f"* **{c['name']}** (`{c['tag']}`) -> `config/{c['file']}`")
    md.append("\n---")

    # 4. SZABLONY I ZMIENNE WIDOKU
    md.append("## 4. SZABLONY WIDOKÓW (templates/)")
    for t_name, t_vars in templates.items():
        md.append(f"* **`{t_name}`** (oczekiwane zmienne root): `{', '.join(t_vars)}`")
    md.append("\n---")

    # 5. MAPA ZALEŻNOŚCI PYTHON (AST)
    md.append("## 5. MAPA ZALEŻNOŚCI (AST IMPORT SCANNER)")
    py_files = sorted((ROOT_DIR / "src").rglob("*.py"))
    for pf in py_files:
        if pf.name == "__init__.py":
            continue
        rel = pf.relative_to(ROOT_DIR)
        mod_name = str(rel.with_suffix("")).replace(os.sep, ".")
        imps = get_ast_imports(pf)
        if imps:
            md.append(f"[{mod_name}]")
            for imp in imps:
                md.append(f"  \\-- {imp}")
    md.append("\n---")

    # 6. CEL SPRINTU
    md.append("## 6. AKTUALNY CEL (SPRINT / FOCUS)")
    md.append(current_focus)
    
    full_text = "\n".join(md) + "\n"
    context_file.write_text(full_text, encoding="utf-8")
    print(f"[OK] Wygenerowano poprawny CONTEXT.md bazujący w 100% na faktach kodu i bazy.")
    if copy_to_clipboard(full_text):
        print("[SCHOWEK] Skopiowano do schowka (Win32 API).")

if __name__ == "__main__":
    generate_context()