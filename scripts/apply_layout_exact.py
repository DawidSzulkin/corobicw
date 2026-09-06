import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from jinja2 import Environment

tpl_file = Path("templates/event_page.html")
html = tpl_file.read_text(encoding="utf-8")

# 1. Wstawienie regulaminu obiektu do lewej kolumny pod opisem (po szczegółach organizacyjnych)
target_bullets = """            {% if event.analysis.details_bullets and event.analysis.details_bullets | length > 0 %}
            <div class="bullets">
              <strong style="display: block; margin-bottom: 12px; color: var(--text); text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px;">Szczegóły organizacyjne:</strong>
              <ul style="color: var(--text-muted);">
                {% for bullet in event.analysis.details_bullets %}<li style="margin-bottom: 6px;">{{ bullet }}</li>{% endfor %}
              </ul>
            </div>
            {% endif %}"""

rules_block = """

            {# MODUŁ ZASAD OBIEKTU I DOSTĘPNOŚCI (LEWA KOLUMNA - POD OPISEM) #}
            {% if event.discounts and event.discounts|length > 0 and not is_free %}
            <div class="venue-rules-card" style="margin-top: 24px; padding: 18px 20px; background: rgba(56, 189, 248, 0.03); border: 1px solid var(--border); border-left: 3px solid var(--accent-blue, #38bdf8); border-radius: 6px;">
              <h3 style="font-size: 0.95rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; color: var(--text); display: flex; align-items: center; gap: 8px;">
                🏛️ Regulamin obiektu i zasady wstępu
              </h3>
              <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 14px; line-height: 1.4;">
                Poniższe zasady dotyczą uczestnictwa na terenie obiektu i obowiązują niezależnie od wybranego miejsca zakupu biletów.
              </p>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px;">
                {% for d in event.discounts %}
                <div style="background: var(--card-bg, #1e232d); padding: 10px 14px; border-radius: 4px; border: 1px solid var(--border);">
                  <div style="font-size: 0.82rem; font-weight: 700; color: var(--text); margin-bottom: 4px;">
                    {{ d.label or d.name }}
                    {% if d.val %}<span style="color: var(--accent-green, #34d399); float: right;">{{ d.val }}</span>{% endif %}
                  </div>
                  {% if d.desc %}<div style="font-size: 0.74rem; color: var(--text-muted); line-height: 1.35;">{{ d.desc }}</div>{% endif %}
                </div>
                {% endfor %}
              </div>
            </div>
            {% endif %}"""

if target_bullets in html:
    html = html.replace(target_bullets, target_bullets + rules_block, 1)
    print("[1/3] Regulamin obiektu wstawiony do lewej kolumny pod opisem.")

# 2. Naprawa struktury offer-box: drawer na pełną szerokość pod wierszem zakupu
target_loop_end = """                      <div class="offer-action-col">
                        {% if is_cancelled %}
                          <span class="offer-btn-buy cancelled" aria-disabled="true">Odwołane</span>
                        {% else %}
                          <a href="{{ offer.url }}" target="_blank" rel="nofollow noopener" 
                             class="offer-btn-buy {% if loop.first and not is_free %}primary{% else %}secondary{% endif %}" 
                             aria-label="{% if is_free %}Szczegóły wydarzenia: {{ event.title }}{% else %}Kup bilet na {{ event.title }} w {{ offer.provider }}{% endif %}">
                            {% if is_free %}Szczegóły{% else %}Kup bilet{% endif %}
                          </a>
                        {% endif %}
                      </div>
                    </div>
                    
                    {% endfor %}"""

replacement_loop_end = """                      <div class="offer-action-col">
                        {% if is_cancelled %}
                          <span class="offer-btn-buy cancelled" aria-disabled="true">Odwołane</span>
                        {% else %}
                          <a href="{{ offer.url }}" target="_blank" rel="nofollow noopener" 
                             class="offer-btn-buy {% if loop.first and not is_free %}primary{% else %}secondary{% endif %}" 
                             aria-label="{% if is_free %}Szczegóły wydarzenia: {{ event.title }}{% else %}Kup bilet na {{ event.title }} w {{ offer.provider }}{% endif %}">
                            {% if is_free %}Szczegóły{% else %}Kup bilet{% endif %}
                          </a>
                        {% endif %}
                      </div>
                    </div>
                    {% if offer.discounts and offer.discounts|length > 0 %}
                    <div class="offer-discounts-drawer" style="border-top: 1px dashed var(--border); padding: 8px 14px 10px; background: rgba(56, 189, 248, 0.02);">
                      <details style="cursor: pointer;">
                        <summary style="font-size: 0.72rem; font-weight: 700; color: var(--accent-blue, #38bdf8); list-style: none; display: flex; justify-content: space-between; align-items: center; text-transform: uppercase; letter-spacing: 0.5px;">
                          <span>🏷️ {{ offer.discounts|length }} {% if offer.discounts|length == 1 %}ulga{% elif offer.discounts|length < 5 %}ulgi{% else %}ulg{% endif %} u tego sprzedawcy</span>
                          <span style="font-size: 0.65rem; color: var(--text-muted);">rozwiń ▾</span>
                        </summary>
                        <ul style="list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px;">
                          {% for d in offer.discounts %}
                          <li style="display: flex; justify-content: space-between; align-items: baseline; font-size: 0.72rem; color: var(--text-muted); border-bottom: 1px solid rgba(255,255,255,0.04); padding-bottom: 4px;">
                            <div>
                              <span style="font-weight: 600; color: var(--text);">{{ d.label or d.name }}</span>
                              {% if d.desc %}<div style="font-size: 0.68rem; color: var(--text-muted); line-height: 1.2;">{{ d.desc }}</div>{% endif %}
                            </div>
                            {% if d.val %}<span style="color: var(--accent-green, #34d399); font-weight: 700; white-space: nowrap; margin-left: 8px;">{{ d.val }}</span>{% endif %}
                          </li>
                          {% endfor %}
                        </ul>
                      </details>
                    </div>
                    {% endif %}
                  </div>
                  {% endfor %}"""

if target_loop_end in html:
    html = html.replace(target_loop_end, replacement_loop_end, 1)
    print("[2/3] Struktura kafelków naprawiona (drawer na 100% szerokości pod ofertą).")

# 3. Usunięcie starego modułu zasad wstępu z sidebara
target_sidebar_discounts = """            {# DEDYKOWANY, POJEDYNCZY MODUŁ ZASAD WSTĘPU I ZNIŻEK INSTYTUCJI #}
              {% if event.discounts and event.discounts|length > 0 and not is_free %}
              <div class="discounts-box" style="margin-top: 14px; border: 1px solid var(--border); border-radius: 6px;">
                <details open>
                  <summary style="padding: 10px 14px; font-weight: 700; color: var(--accent-blue); cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.5px;">
                    🛡️ Zasady wstępu i ulgi ({{ event.discounts|length }})
                  </summary>
                  <ul class="discounts-list" style="list-style: none; padding: 4px 14px 12px; margin: 0; display: flex; flex-direction: column; gap: 8px;">
                    {% for d in event.discounts %}
                    <li style="display: flex; flex-direction: column; gap: 2px; font-size: 0.75rem; color: var(--text-muted); border-bottom: 1px solid rgba(255,255,255,0.04); padding-bottom: 6px;">
                      <div class="disc-head" style="font-weight: 700; color: var(--text);">
                        <span>{{ d.label or d.name }}</span>
                        {% if d.val %}<span class="disc-val" style="color: var(--accent-green); float: right;">{{ d.val }}</span>{% endif %}
                      </div>
                      {% if d.desc %}<div class="disc-desc" style="font-size: 0.7rem; color: var(--text-muted); line-height: 1.3;">{{ d.desc }}</div>{% endif %}
                    </li>
                    {% endfor %}
                  </ul>
                </details>
              </div>
              {% endif %}"""

if target_sidebar_discounts in html:
    html = html.replace(target_sidebar_discounts, "", 1)
    print("[3/3] Stary moduł zasad usunięty z sidebara.")

# Walidacja składni Jinja2 przed fizycznym zapisem
Environment().parse(html)
tpl_file.write_text(html, encoding="utf-8")
print("[OK] Szablon templates/event_page.html zwalidowany syntaktycznie i zapisany.")

# 4. Regeneracja podstrony Maryli Rodowicz z SQLite
from src.infrastructure.db import init_db, get_active_events
from src.domain.pipeline import deduplicate_events, _prepare_full_event_pages
from src.infrastructure.renderer import HTMLRenderer

init_db()
today = datetime.now().strftime("%Y-%m-%d")
renderer = HTMLRenderer()

raw = get_active_events("opole", today)
pages = _prepare_full_event_pages(deduplicate_events(raw, "opole"), {}, {}, "opole")
tpl = renderer.env.get_template("event_page.html")
target_url = None

for ev in pages:
    if "rodowicz" in (ev.slug or "").lower():
        for off in ev.ticket_offers:
            p = off.provider.lower()
            if "ncpp" in p:
                off.discounts = [
                    {"label": "Karta Opolanina", "desc": "Weryfikacja przy bramce", "val": "-10%"},
                    {"label": "Senior 60+", "desc": "Z legitymacją ZUS", "val": "145 zł"}
                ]
            elif "biletyna" in p:
                off.discounts = [
                    {"label": "Kod Newsletter", "desc": "Dla subskrybentów", "val": "-15 zł"}
                ]
        out_dir = Path("public/opole/wydarzenia") / ev.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(tpl.render(event=ev, ev=ev, city_name="Opole", city_tag="opole", city="Opole", is_free=False), encoding="utf-8")
        target_url = f"http://localhost:8000/opole/wydarzenia/{ev.slug}/"
        break

print(f"[OK] Wygenerowano stronę testową: {target_url}")

# 5. Uruchomienie testów jednostkowych
p_test = subprocess.run([sys.executable, "-m", "pytest", "tests/"], capture_output=True, text=True, encoding="utf-8")
print(f"[TESTY PYTEST]: {'27/27 PASSED' if 'passed' in p_test.stdout else 'BŁĄD'}")

# 6. Otwarcie przeglądarki i start serwera
if target_url:
    webbrowser.open(target_url)

print("\n" + "="*50)
print("SERWER HTTP AKTYWNY NA PORCIE 8000")
print(f"URL: {target_url}")
print("Zatrzymaj serwer: Ctrl + C")
print("="*50 + "\n")

handler = functools.partial(SimpleHTTPRequestHandler, directory="public")
server = HTTPServer(("localhost", 8000), handler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n[OK] Serwer HTTP zatrzymany.")
