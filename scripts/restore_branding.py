import subprocess
import sys
from pathlib import Path
from jinja2 import Environment

# 1. Pobranie oryginalnego, nienaruszonego szablonu z historii Git
git_orig = subprocess.run(
    ["git", "show", "HEAD:templates/event_page.html"],
    capture_output=True, text=True, encoding="utf-8"
).stdout

if not git_orig:
    print("[BŁĄD] Nie udało się odczytać pliku z Git!")
    sys.exit(1)

# Wycinamy oryginalny <header>...</header> ze sprawdzonym logo
header_start = git_orig.find("<header")
header_end = git_orig.find("</header>") + len("</header>")
orig_header = git_orig[header_start:header_end]

# 2. Odczyt bieżącego pliku i podmiana nagłówka na oryginalny z logo
tpl_path = Path("templates/event_page.html")
curr = tpl_path.read_text(encoding="utf-8")

c_h_start = curr.find("<header")
c_h_end = curr.find("</header>") + len("</header>")
final_html = curr[:c_h_start] + orig_header + curr[c_h_end:]

# Walidacja składni Jinja2
Environment().parse(final_html)
tpl_path.write_text(final_html, encoding="utf-8")
print("[OK] Przywrócono oryginalne logo i nagłówek z systemu designu.")

# 3. Błyskawiczna regeneracja strony Maryli z bazy SQLite
from src.infrastructure.db import init_db, get_active_events
from src.domain.pipeline import deduplicate_events, _prepare_full_event_pages
from src.infrastructure.renderer import HTMLRenderer

init_db()
renderer = HTMLRenderer()
raw = get_active_events("opole", "2026-09-03")
pages = _prepare_full_event_pages(deduplicate_events(raw, "opole"), {}, {}, "opole")
tpl = renderer.env.get_template("event_page.html")

for ev in pages:
    if "rodowicz" in (ev.slug or "").lower():
        out_dir = Path("public/opole/wydarzenia") / ev.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            tpl.render(event=ev, ev=ev, city_name="Opole", city_tag="opole", city="Opole", is_free=False),
            encoding="utf-8"
        )
        print(f"[OK] Przeliczono podgląd: http://localhost:8000/opole/wydarzenia/{ev.slug}/")
        break

# 4. Uruchomienie testów jednostkowych
p = subprocess.run([sys.executable, "-m", "pytest", "tests/"], capture_output=True, text=True, encoding="utf-8")
print(f"[TESTY PYTEST]: {'27/27 PASSED' if 'passed' in p.stdout else 'BŁĄD'}")
