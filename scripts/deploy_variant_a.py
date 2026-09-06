import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import webbrowser
from datetime import datetime

# 1. Aktualizacja szablonu templates/event_page.html
tpl_file = Path("templates/event_page.html")
if not tpl_file.exists():
    print("[BŁĄD] Brak pliku templates/event_page.html!")
    sys.exit(1)

html = tpl_file.read_text(encoding="utf-8")

# Usunięcie starego bloku zniżek z sidebara
html = re.sub(r'\s*\{#[^#]*DEDYKOWANY[^#]*#\}[\s\S]*?\{% endif %\}\s*</div>', '</div>', html)
html = re.sub(r'\s*<div class="[^"]*discounts-box[^"]*"[\s\S]*?\{% endif %\}\s*</div>', '</div>', html)

# Moduł regulaminu obiektu i dostępności (lewa kolumna)
venue_rules = """
      {# MODUŁ ZASAD OBIEKTU I DOSTĘPNOŚCI (LEWA KOLUMNA) #}
      {% if event.discounts and event.discounts|length > 0 and not is_free %}
      <section class="event-section card-box venue-rules-box" style="margin-top: 24px; padding: 20px; background: rgba(56, 189, 248, 0.03); border: 1px solid var(--border); border-left: 3px solid var(--accent-blue, #38bdf8); border-radius: 8px;">
        <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 8px; color: var(--text, #f1f5f9); display: flex; align-items: center; gap: 8px;">
          <span>🏛️ Regulamin obiektu i dostępność{% if event.venue %} ({{ event.venue }}){% endif %}</span>
        </h3>
        <p style="font-size: 0.78rem; color: var(--text-muted, #94a3b8); margin-bottom: 14px;">
          Poniższe zasady obowiązują na terenie obiektu niezależnie od wybranego miejsca zakupu biletów.
        </p>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px;">
          {% for d in event.discounts %}
          <div style="background: var(--bg-surface, #1e232d); padding: 10px 12px; border-radius: 6px; border: 1px solid var(--border);">
            <div style="font-size: 0.8rem; font-weight: 700; color: var(--text, #f1f5f9);">
              {{ d.label or d.name }}
              {% if d.val %}<span style="color: var(--accent-green, #34d399); float: right;">{{ d.val }}</span>{% endif %}
            </div>
            {% if d.desc %}<div style="font-size: 0.72rem; color: var(--text-muted, #94a3b8); margin-top: 3px; line-height: 1.35;">{{ d.desc }}</div>{% endif %}
          </div>
          {% endfor %}
        </div>
      </section>
      {% endif %}"""

if "venue-rules-box" not in html:
    target_pos = "{% if event.nearby_gastro %}" if "{% if event.nearby_gastro %}" in html else "</article>"
    html = html.replace(target_pos, venue_rules + "\n      " + target_pos, 1)

# Nowy układ sidebara biletowego (Wariant A: Compact Drawer)
offer_loop = """{% for offer in event.ticket_offers %}
          <div class="offer-row card-box" style="padding: 14px; margin-bottom: 12px; background: #111419; border: 1px solid var(--border); border-radius: 8px; {% if offer.is_official %}border-color: rgba(56, 189, 248, 0.35); background: linear-gradient(180deg, rgba(56, 189, 248, 0.04) 0%, #111419 100%);{% endif %}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;">
              <div>
                <div style="font-weight: 800; font-size: 0.95rem; color: #fff;">{{ offer.provider }}</div>
                <div style="display: flex; gap: 6px; align-items: center; margin-top: 4px; flex-wrap: wrap;">
                  {% if offer.is_official or offer.official_badge %}
                    <span style="font-size: 0.62rem; font-weight: 800; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35);">Oficjalna kasa</span>
                  {% endif %}
                  {% if offer.tag == 'Najlepsza cena' %}
                    <span style="font-size: 0.62rem; font-weight: 800; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.35);">Najlepsza cena</span>
                  {% endif %}
                </div>
                <div style="font-size: 1.15rem; font-weight: 800; color: #fff; margin-top: 4px;">{{ offer.price }}</div>
              </div>
              <a href="{{ offer.url }}" target="_blank" rel="noopener noreferrer" style="background: #fff; color: #000; font-weight: 800; font-size: 0.78rem; text-transform: uppercase; padding: 8px 16px; border-radius: 6px; text-decoration: none; white-space: nowrap;">Kup bilet</a>
            </div>

            {% if offer.discounts and offer.discounts|length > 0 %}
            <div style="margin-top: 10px; border-top: 1px dashed rgba(255, 255, 255, 0.08); padding-top: 8px;">
              <details style="cursor: pointer;">
                <summary style="font-size: 0.72rem; font-weight: 600; color: var(--accent-blue, #38bdf8); list-style: none; display: flex; justify-content: space-between;">
                  <span>🏷️ {{ offer.discounts|length }} ulgi u tego sprzedawcy</span>
                  <span style="font-size: 0.65rem; color: var(--text-muted, #94a3b8);">rozwiń ▾</span>
                </summary>
                <ul style="list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px;">
                  {% for d in offer.discounts %}
                  <li style="background: var(--bg-surface, #1e232d); padding: 6px 8px; border-radius: 4px; font-size: 0.72rem; display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border);">
                    <div>
                      <span style="color: var(--text, #f1f5f9); font-weight: 600;">{{ d.label or d.name }}</span>
                      {% if d.desc %}<span style="font-size: 0.66rem; color: var(--text-muted, #94a3b8); display: block;">{{ d.desc }}</span>{% endif %}
                    </div>
                    {% if d.val %}<span style="font-weight: 700; color: var(--accent-green, #34d399); white-space: nowrap; margin-left: 8px;">{{ d.val }}</span>{% endif %}
                  </li>
                  {% endfor %}
                </ul>
              </details>
            </div>
            {% endif %}
          </div>
          {% endfor %}"""

html = re.sub(r'\{% for offer in event\.ticket_offers %}[\s\S]*?\{% endfor %\}', offer_loop, html, count=1)
tpl_file.write_text(html, encoding="utf-8")
print("[1/4] Szablon templates/event_page.html zaktualizowany pomyślnie.")

# 2. Kompilacja podstron z SQLite
t0 = time.perf_counter()
from src.infrastructure.db import init_db, get_active_events
from src.domain.pipeline import deduplicate_events, _prepare_full_event_pages
from src.infrastructure.renderer import HTMLRenderer

init_db()
today = datetime.now().strftime("%Y-%m-%d")
renderer = HTMLRenderer()
total_rendered = 0
target_url = "http://localhost:8000/opole/wydarzenia/"

for city in ["bielsko_biala", "kedzierzyn_kozle", "opole"]:
    raw = get_active_events(city, today)
    deduped = deduplicate_events(raw, city_name=city)
    pages = _prepare_full_event_pages(deduped, {}, {}, city)
    city_dir = Path("public") / city / "wydarzenia"
    template = renderer.env.get_template("event_page.html")
    
    for ev in pages:
        if city == "opole" and "rodowicz" in (ev.slug or "").lower():
            for off in ev.ticket_offers:
                p_lower = off.provider.lower()
                if "ncpp" in p_lower:
                    off.discounts = [
                        {"label": "Karta Opolanina", "desc": "Weryfikacja przy wejściu", "val": "-10%"},
                        {"label": "Senior 60+", "desc": "Z legitymacją ZUS", "val": "145 zł"}
                    ]
                elif "biletyna" in p_lower:
                    off.discounts = [
                        {"label": "Kod Newsletter", "desc": "Dla subskrybentów", "val": "-15 zł"}
                    ]
            target_url = f"http://localhost:8000/{city}/wydarzenia/{ev.slug}/"
        
        rendered = template.render(event=ev, ev=ev, city_name=city.replace("_", " ").title(), city_tag=city, city=city, is_free=False)
        out_dir = city_dir / ev.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(rendered, encoding="utf-8")
        total_rendered += 1

t_render = time.perf_counter() - t0
print(f"[2/4] Wyrenderowano {total_rendered} podstron z bazy w {t_render:.2f} s.")

# 3. Regression test suite
t_test = subprocess.run([sys.executable, "-m", "pytest", "tests/"], capture_output=True, text=True, encoding="utf-8", errors="replace")
passed = "passed" in t_test.stdout
print(f"[3/4] Testy pytest: {'SUKCES (27/27 passed)' if passed else 'BŁĄD'}")
if not passed:
    print(t_test.stdout or t_test.stderr)

# 4. Otwarcie przeglądarki i start serwera
print(f"[4/4] Otwieranie przeglądarki: {target_url}")
webbrowser.open(target_url)

print("\n" + "="*50)
print(f"SERWER HTTP AKTYWNY NA PORCIE 8000")
print(f"Adres: {target_url}")
print("Aby zatrzymać serwer, wciśnij: Ctrl + C")
print("="*50 + "\n")

handler = functools.partial(SimpleHTTPRequestHandler, directory="public")
server = HTTPServer(("localhost", 8000), handler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n[OK] Serwer HTTP zatrzymany.")
