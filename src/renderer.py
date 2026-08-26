import os
from pathlib import Path
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader
from src.models import FullEventPage


class HTMLRenderer:
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def render_portal_hub(self, active_cities: List[Dict[str, str]], output_dir: str = "docs"):
        os.makedirs(output_dir, exist_ok=True)
        template = self.env.get_template("portal_hub.html")
        html_out = template.render(cities=active_cities)

        hub_path = os.path.join(output_dir, "index.html")
        with open(hub_path, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"[RENDERER] Strona główna portalu (Wybór miast): {hub_path}")

    def render_city(self, city_name: str, city_tag: str, events: List[FullEventPage], output_dir: str = "docs"):
        city_dir = Path(output_dir) / city_tag
        events_dir = city_dir / "wydarzenia"
        events_dir.mkdir(parents=True, exist_ok=True)

        # 1. Podstrony pojedynczych aktywnych wydarzeń
        event_template = self.env.get_template("event_page.html")
        active_filenames = set()

        for ev in events:
            filename = f"{ev.slug}.html"
            active_filenames.add(filename)
            single_html = event_template.render(city=city_name, city_tag=city_tag, event=ev)
            single_file = events_dir / filename
            with open(single_file, "w", encoding="utf-8") as f:
                f.write(single_html)

        # 2. Czyszczenie osieroconych plików HTML (retencja)
        removed_count = 0
        for existing_file in events_dir.glob("*.html"):
            if existing_file.name not in active_filenames:
                try:
                    existing_file.unlink()
                    removed_count += 1
                except Exception as e:
                    print(f"[RENDERER] Błąd usuwania osieroconego pliku {existing_file.name}: {e}")

        # 3. Katalog miejski (siatka kafelków)
        home_template = self.env.get_template("home.html")
        home_html = home_template.render(city=city_name, city_tag=city_tag, events=events)
        home_file = city_dir / "index.html"
        with open(home_file, "w", encoding="utf-8") as f:
            f.write(home_html)

        print(f"[RENDERER] Katalog miasta ({city_name}): {home_file}")
        print(f"[RENDERER] Wygenerowano {len(events)} podstron, usunięto {removed_count} nieaktywnych w: {events_dir}/")
