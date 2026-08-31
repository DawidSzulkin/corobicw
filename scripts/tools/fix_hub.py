from pathlib import Path
import re

hub_template_path = Path("templates/portal_hub.html")
if not hub_template_path.exists():
    print("[BŁĄD] Brak pliku templates/portal_hub.html")
    exit(1)

with open(hub_template_path, "r", encoding="utf-8") as f:
    template_content = f.read()

print("--- ORYGINALNY SZABLON (FRAGMENT KAFELKÓW) ---")
print(template_content[:800])
print("---------------------------------------------")

# Dynamiczny blok generowania kafelków miast dla Jinja2
dynamic_grid = """
    <div class="cities-grid">
      {% for c in cities %}
      <div class="city-card">
        <h2>{{ c.name.upper() }}</h2>
        <a href="/{{ c.tag }}/" class="city-link">OTWÓRZ AGENDĘ &rarr;</a>
        <div class="badge">WYDANIE AKTYWNE</div>
      </div>
      {% endfor %}
    </div>
"""

# Zastąpienie sztywnych kafelków pętlą dynamiczną
if "{% for" not in template_content:
    # Wymiana sekcji z kafelkami
    template_content = re.sub(
        r'(<div[^>]*class=["\'][^"\']*grid[^"\']*["\'][^>]*>)(.*?)(</div>\s*</div>|\Z)',
        r'\1\n' + dynamic_grid + r'\n</div>',
        template_content,
        flags=re.DOTALL | re.IGNORECASE
    )
    with open(hub_template_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    print("[OK] Zaktualizowano templates/portal_hub.html o dynamiczną pętlę Jinja2.")
else:
    print("[INFO] Szablon zawiera już pętlę Jinja2 - weryfikacja zmiennych.")
