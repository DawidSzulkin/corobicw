import re
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 1. Dodanie premium_venues do opole.yaml
cfg_path = BASE_DIR / "config" / "opole.yaml"
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

cfg["premium_venues"] = [
    "o-narodowe-centrum-polskiej-piosenki",
    "o-teatr-dramatyczny-im-jana-kochanowskiego",
    "o-filharmonia-opolska",
    "o-opo",
    "o-hala-sportowa-politechniki-opolskiej",
    "o-muzeum-polskiej-piosenki",
    "o-teatr-lalki-i-aktora"
]

with open(cfg_path, "w", encoding="utf-8") as f:
    yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

# 2. Modyfikacja renderer.py - obsługa flagi premium
renderer_path = BASE_DIR / "src" / "infrastructure" / "renderer.py"
with open(renderer_path, "r", encoding="utf-8") as f:
    content = f.read()

# Szukamy miejsca, gdzie zdefiniowana jest metoda render_city
# Musimy pobrać city_cfg aby móc z niego odczytać premium_venues.
# W klasie HTMLRenderer dodajemy odczyt premium_venues do funkcji.
# Aktualnie funkcja wygląda tak: def render_city(self, city_name: str, city_tag: str, events: List[FullEventPage], places: Dict[str, Dict[str, Any]], output_dir: str = "public"):
# Mamy mały problem, bo nie przekazujemy city_cfg do renderer.render_city() w potoku.
# Prostsze rozwiązanie architektoniczne to sprawdzanie znacznika np. data.get("group") == "kultura" 
# LUB po prostu dodanie parametru city_cfg. Zróbmy to mądrze przez regex.

new_logic = """
        # --- LOGIKA PREMIUM VENUES ---
        premium_venues = []
        cfg_file = Path("config") / f"{city_tag}.yaml"
        if cfg_file.exists():
            import yaml
            with open(cfg_file, "r", encoding="utf-8") as yf:
                city_data = yaml.safe_load(yf) or {}
                premium_venues = city_data.get("premium_venues", [])
        
        place_template = self.env.get_template("place_page.html")
        rendered_places = 0
        for place_id, place_data in places.items():
            upcoming = [ev for ev in events if ev.place_id == place_id or ev.analysis.ticket_info.place_id == place_id]
            
            is_premium = place_id in premium_venues or place_data.get("group") in ["kultura", "theatre"]
            if not upcoming and not is_premium:
                continue
            
            p_folder = places_dir / place_id
"""

# Zastąpienie pętli for place_id
content = re.sub(
    r'place_template = self\.env\.get_template\("place_page\.html"\)\s+rendered_places = 0\s+for place_id, place_data in places\.items\(\):.*?(p_folder = places_dir / place_id)',
    new_logic.strip(),
    content,
    flags=re.DOTALL
)

with open(renderer_path, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] Zaktualizowano model architektoniczny miejsc (Premium vs Transient).")
