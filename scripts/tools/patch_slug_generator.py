import re
from pathlib import Path

src_dir = Path("src")
target_file = None

for py_file in src_dir.rglob("*.py"):
    content = py_file.read_text(encoding="utf-8")
    if "def _prepare_event_models" in content and "slugify" in content:
        target_file = py_file
        break

if not target_file:
    print("[!] Nie znaleziono pliku z funkcją _prepare_event_models.")
    exit(1)

print(f"[*] Znaleziono plik: {target_file}")
code = target_file.read_text(encoding="utf-8")

# 1. Definicja deterministycznego generatora slugów
slug_helper_func = '''
def _generate_event_slug(title: str, date_start: str, time_start: str, seen_slugs: set) -> str:
    base = slugify(title) or "wydarzenie"
    clean_date = date_start.strip()[:10]
    candidate = f"{base}-{clean_date}" if clean_date else base
    
    if candidate not in seen_slugs:
        seen_slugs.add(candidate)
        return candidate
        
    # Kolizja: dopisujemy godzinę rozpoczęcia (HHMM)
    clean_time = re.sub(r'[^0-9]', '', str(time_start))[:4]
    if clean_time:
        time_candidate = f"{candidate}-{clean_time}"
        if time_candidate not in seen_slugs:
            seen_slugs.add(time_candidate)
            return time_candidate
            
    # Fallback przy identycznej dacie i godzinie: deterministyczny licznik
    idx = 2
    while f"{candidate}-{idx}" in seen_slugs:
        idx += 1
    final_slug = f"{candidate}-{idx}"
    seen_slugs.add(final_slug)
    return final_slug
'''

# 2. Wstrzyknięcie pomocnika przed _prepare_event_models, jeśli jeszcze go nie ma
if "_generate_event_slug" not in code:
    code = code.replace("def _prepare_event_models", slug_helper_func.strip() + "\n\n\ndef _prepare_event_models")

# 3. Inicjalizacja zbioru seen_slugs w _prepare_event_models
code = re.sub(
    r'(def _prepare_event_models\([^)]*\)\s*->\s*List\[FullEventPage\]:\s*\n\s*models:\s*List\[FullEventPage\]\s*=\s*\[\])',
    r'\1\n    seen_slugs: set = set()',
    code
)

# 4. Podmiana generowania sluga w pętli
old_slug_pattern = r'slug\s*=\s*slugify\([^)]+\)'
new_slug_logic = 'slug = _generate_event_slug(title, date_start, time_start, seen_slugs)'

code = re.sub(old_slug_pattern, new_slug_logic, code)

target_file.write_text(code, encoding="utf-8")
print(f"[OK] Zaktualizowano generator slugów w {target_file}.")
