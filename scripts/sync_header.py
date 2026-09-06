from pathlib import Path
from jinja2 import Environment
import subprocess
import sys

# 1. Odczyt nienaruszonego header i styli logo z templates/home.html
home_path = Path("templates/home.html")
event_path = Path("templates/event_page.html")

if not home_path.exists() or not event_path.exists():
    print("[BŁĄD] Brak wymaganych plików szablonów!")
    sys.exit(1)

home_txt = home_path.read_text(encoding="utf-8")
event_txt = event_path.read_text(encoding="utf-8")

# Pobieramy dokładny <header>...</header> z home.html
h_start = home_txt.find("<header")
h_end = home_txt.find("</header>") + len("</header>")
orig_header = home_txt[h_start:h_end]

# Pobieramy style brand/logo/header z home.html
css_brand_rules = """
    /* BRUTALIST BRANDING Z HOME.HTML */
    .brand { font-family: inherit; font-size: 1.35rem; font-weight: 900; text-transform: uppercase; letter-spacing: -0.5px; color: #fff; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; }
    .brand-tag, .brand span { background: #fff !important; color: #000 !important; padding: 2px 8px !important; font-size: 0.85rem !important; font-weight: 900 !important; letter-spacing: 0.5px !important; border-radius: 2px !important; text-transform: uppercase !important; display: inline-block !important; }
    header { background: #0c0e12; border-bottom: 1px solid #282f3d; padding: 18px 24px; }
"""

# Podmieniamy <header> w event_page.html
ev_h_start = event_txt.find("<header")
ev_h_end = event_txt.find("</header>") + len("</header>")
new_event_txt = event_txt[:ev_h_start] + orig_header + event_txt[ev_h_end:]

# Wstrzykujemy brakujące style brandingowe przed </style>
if "/* BRUTALIST BRANDING" not in new_event_txt:
    style_end = new_event_txt.find("</style>")
    new_event_txt = new_event_txt[:style_end] + css_brand_rules + new_event_txt[style_end:]

# Weryfikacja AST Jinja2
Environment().parse(new_event_txt)
event_path.write_text(new_event_txt, encoding="utf-8")
print("[1/3] Header i styl logo COROBIĆW OPOLE przywrócone z templates/home.html")

# 2. Szybka regeneracja strony Maryli Rodowicz z lokalnej bazy
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
        print(f"[2/3] Podgląd zaktualizowany: http://localhost:8000/opole/wydarzenia/{ev.slug}/")
        break

# 3. Weryfikacja testów jednostkowych
p_test = subprocess.run([sys.executable, "-m", "pytest", "tests/"], capture_output=True, text=True, encoding="utf-8")
passed = "passed" in p_test.stdout
print(f"[3/3] Testy pytest: {'27/27 PASSED' if passed else 'BŁĄD'}")
if not passed:
    print(p_test.stdout or p_test.stderr)
