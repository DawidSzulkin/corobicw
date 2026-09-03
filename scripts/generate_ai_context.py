import os
import ast
from pathlib import Path
from datetime import datetime

STATIC_HEADER = """# PROJEKT: CoRobićW - Architektura, Kontekst i Protokół Operacyjny
Data wygenerowania: {date}

Jesteś krytycznym partnerem technicznym i senior full-stack developerem pracującym nad agregatorem "CoRobićW".
Nie jesteś potakującym asystentem. Szukaj luk logicznych i długów technologicznych. Do każdego wytkniętego problemu MUSISZ przedstawić konkretną propozycję rozwiązania lub zoptymalizowany kod.

---
## 1. PROTOKÓŁ KOMUNIKACJI (ZASADA ZERO)
1. **PowerShell & UTF-8:** Każdy skrypt operacyjny MUSI zaczynać się od `$env:PYTHONIOENCODING = "utf-8"`.
2. **Bezpieczne modyfikacje:** Zakaz używania złożonych Regexów do modyfikacji HTML/kodu. Używaj bezpiecznego indeksowania (`str.find`) lub parserów.
3. **Schowek:** Skrypty raportujące muszą kopiować wynik do schowka (`| Set-Clipboard`).

---
## 2. STOS TECHNOLOGICZNY I ARCHITEKTURA
* **Backend:** Python 3.11+, ETL Pipeline (`src/domain/pipeline.py`).
* **Baza Danych:** SQLite (`data/events.db` - produkcyjna, `data/http_cache.sqlite` - kesz).
* **Frontend:** Static Site Generator (SSG) - Jinja2, CSS Grid.

---
## 3. STRUKTURA DANYCH (KONTRAKT)
Zawsze używaj poniższej konwencji nazewniczej dla obiektu Event:
* title (str) - Tytuł
* date_start (str) - Data ISO (YYYY-MM-DD)
* source_url (str) - Oryginalny link
* ticket_offers (list) - Tablica ofert: [{"provider": str, "price": str, "url": str, "discounts": [{"name": str, "val": str}]}]
* analysis (dict) - Dane z AI: ticket_info.price_range, ticket_info.venue_name, quick_facts, full_description.

---
## 4. TWARDE REGUŁY PROJEKTOWE (GUARDRAILS)
* **ZAKAZ Shallow Scraping:** Scraper musi wykonywać Deep Scraping na podstronach szczegółowych.
* **Moduł Biletowy (Ceneo-Style):** Płaska lista w grid-template-columns: 1fr auto. Brak Hero CTA. Zniżki w <details>.
* **Deduplikacja:** W oparciu o provider i wyczyszczony URL (bez query params).
"""

FOCUS_SECTION = """---
## 6. AKTUALNY CEL (SPRINT / FOCUS)
[!!! TUTAJ WPISZ SWÓJ AKTUALNY PROBLEM LUB CEL PRZED WKLEJENIEM DO AI !!!]
Cel: 
Problem: 
"""

def generate_tree(startpath="."):
    ignore_dirs = {
        '.git', '__pycache__', 'env', 'venv', 'node_modules', '.pytest_cache',
        'bielsko_biala', 'kedzierzyn_kozle', 'opole', 'assets', 'archive', 'public', 'docs'
    }
    # Katalogi, których nie rozwijamy szczegółowo, aby chronić okno tokenów
    collapse_dirs = {'tools', 'generators'}
    
    tree = []
    base_path = Path(startpath).resolve()
    tree.append(f"{base_path.name}/")
    
    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        rel_parts = Path(root).relative_to(base_path).parts
        level = len(rel_parts)
        
        if level == 0:
            # Pliki w roocie
            root_files = [f for f in files if f in ['run.py', 'Update-Context.bat', 'CONTEXT.md']]
            for f in sorted(root_files):
                tree.append(f"|-- {f}")
            continue
            
        folder_name = rel_parts[-1]
        indent = '|   ' * (level - 1)
        
        # Jeśli folder jest w liście do zwinięcia, raportujemy tylko jego obecność
        if folder_name in collapse_dirs:
            dirs.clear() # nie wchodź głębiej
            tree.append(f"{indent}|-- {folder_name}/ (zawiera {len(files)} skryptów pomocniczych)")
            continue
            
        tree.append(f"{indent}|-- {folder_name}/")
        subindent = '|   ' * level
        
        valid_files = [
            f for f in files 
            if f.endswith(('.py', '.yaml', '.json', '.db', '.sqlite', '.bat', '.md')) 
            or (f.endswith('.html') and 'templates' in rel_parts)
        ]
        for f in sorted(valid_files):
            tree.append(f"{subindent}|-- {f}")
            
    return "\n".join(tree)

def map_dependencies(src_dir="src"):
    src_path = Path(src_dir)
    if not src_path.exists():
        return "Katalog src/ nie istnieje."
    
    deps_map = {}
    for py_file in src_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        module_name = str(py_file.relative_to(src_path.parent)).replace(os.sep, ".").replace(".py", "")
        
        try:
            with open(py_file, 'r', encoding='utf-8-sig') as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            
            local_imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("src.") or node.level > 0:
                        local_imports.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src."):
                            local_imports.add(alias.name)
            if local_imports:
                deps_map[module_name] = sorted(list(local_imports))
        except SyntaxError as e:
            deps_map[module_name] = [f"<BLAD SKLADNI: Linia {e.lineno} -> {e.msg}>"]
        except Exception as e:
            deps_map[module_name] = [f"<BLAD PARSOWANIA: {e}>"]
            
    out = []
    for mod in sorted(deps_map.keys()):
        out.append(f"[{mod}]")
        for dep in deps_map[mod]:
            out.append(f"  \\-- {dep}")
    return "\n".join(out)

if __name__ == "__main__":
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = STATIC_HEADER.replace("{date}", now)
    tree_str = generate_tree(".")
    deps_str = map_dependencies("src")
    
    full_context = f"{header}\n---\n## 5. STRUKTURA I ZALEŻNOŚCI (AUTO-MAPOWANIE)\n\n### Drzewo plików\n```text\n{tree_str}\n```\n\n### Mapa Zależności (Importy Wewnętrzne)\n```text\n{deps_str}\n```\n\n{FOCUS_SECTION}"
    Path("CONTEXT.md").write_text(full_context, encoding="utf-8")
    print("[SUKCES] Wygenerowano poprawny, zoptymalizowany CONTEXT.md")