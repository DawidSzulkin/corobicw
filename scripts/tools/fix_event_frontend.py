import re
from pathlib import Path

template_path = Path("templates/event_page.html")
if not template_path.exists():
    print("[!] Brak pliku templates/event_page.html")
    exit(1)

with open(template_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Dodanie pola "Organizator" nad miejscem (jeśli istnieje)
organizer_block = """
          <div class="meta-row">
            <span class="meta-label">ORGANIZATOR</span>
            <span class="meta-value">{{ event.analysis.organizer or "Organizator lokalny" }}</span>
          </div>
"""
if "ORGANIZATOR" not in content:
    content = re.sub(
        r'(<div class="meta-row">\s*<span class="meta-label">MIEJSCE</span>)',
        organizer_block + r'\n          \1',
        content
    )

# 2. Zabezpieczenie wyświetlania miejsca dla eventów plenerowych
miejsce_replace = """
          <div class="meta-row">
            <span class="meta-label">MIEJSCE</span>
            <span class="meta-value">
              {% if event.place_id %}
                <a href="/{{ event.city_tag | default('miasto') }}/miejsca/{{ event.place_id }}/" class="venue-link" style="color: var(--text); text-decoration: underline; text-underline-offset: 4px;">{{ event.analysis.ticket_info.venue_name }}</a>
              {% else %}
                {{ event.analysis.ticket_info.venue_name or event.analysis.address or "Przestrzeń miejska / Wydarzenie plenerowe" }}
              {% endif %}
            </span>
          </div>
"""
# Uproszczona podmiana całego bloku "MIEJSCE"
content = re.sub(
    r'<div class="meta-row">\s*<span class="meta-label">MIEJSCE</span>.*?</div>',
    miejsce_replace.strip(),
    content,
    flags=re.DOTALL
)

# 3. Zabezpieczenie sekcji z parkingiem (pokazuj tylko, gdy jest miejsce)
parking_replace = """
          {% if event.place_id %}
          <div class="meta-row">
            <span class="meta-label">PARKING</span>
            <span class="meta-value">{{ event.analysis.quick_facts.parking }}</span>
          </div>
          {% endif %}
"""
content = re.sub(
    r'<div class="meta-row">\s*<span class="meta-label">PARKING</span>.*?</div>',
    parking_replace.strip(),
    content,
    flags=re.DOTALL
)

# 4. Zabezpieczenie modułu mapy i gastro (całe sekcje "Gdzie zjeść" i "Mapa")
if "{% if event.place_id %}" not in content.split("<!-- LOGISTYKA -->")[0] and "id=\"map\"" in content:
    # Owijamy mapę i gastro w IF-a
    content = re.sub(
        r'(<h2 class="section-title">Gdzie zjeść.*?</div>\s*</div>)',
        r'{% if event.place_id %}\n        \1\n        {% endif %}',
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r'(<h2 class="section-title">Lokalizacja.*?<div id="map" class="map-container"></div>)',
        r'{% if event.place_id %}\n        \1\n        {% endif %}',
        content,
        flags=re.DOTALL
    )

with open(template_path, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] Szablon event_page.html zaktualizowany (obsługa pleneru i organizatorów).")
