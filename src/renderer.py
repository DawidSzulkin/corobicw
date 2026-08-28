import hashlib
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader
from src.models import FullEventPage


class HTMLRenderer:

    def _load_build_cache(self) -> dict:
        cache_path = Path("data/.build_cache.json")
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"places": {}, "events": {}}
        return {"places": {}, "events": {}}

    def _save_build_cache(self, cache: dict):
        cache_path = Path("data/.build_cache.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CACHE] Błąd zapisu cache: {e}")

    def _calculate_hash(self, data: any) -> str:
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def _sync_assets(self, output_dir: str):
        out_assets = Path(output_dir) / "assets"
        src_assets = Path("assets") if Path("assets").exists() else Path("docs/assets")
        if src_assets.exists():
            out_assets.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_assets, out_assets, dirs_exist_ok=True)

    def render_portal_hub(self, active_cities: List[Dict[str, str]], output_dir: str = "public"):
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        self._sync_assets(output_dir)

        template = self.env.get_template("portal_hub.html")
        html_out = template.render(cities=active_cities)

        hub_file = out_path / "index.html"
        with open(hub_file, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"[RENDERER] Strona główna portalu (Wybór miast): {hub_file}")

    def render_city(self, city_name: str, city_tag: str, events: List[FullEventPage], places: Dict[str, Dict[str, Any]], output_dir: str = "public"):
        city_dir = Path(output_dir) / city_tag
        events_dir = city_dir / "wydarzenia"
        places_dir = city_dir / "miejsca"

        self._sync_assets(output_dir)

        # 1. Czyszczenie i renderowanie podstron wydarzeń
        if events_dir.exists():
            shutil.rmtree(events_dir)
        events_dir.mkdir(parents=True, exist_ok=True)

        event_template = self.env.get_template("event_page.html")
        for ev in events:
            single_folder = events_dir / ev.slug
            single_folder.mkdir(parents=True, exist_ok=True)
            single_file = single_folder / "index.html"
            
            single_html = event_template.render(city=city_name, city_tag=city_tag, event=ev)
            with open(single_file, "w", encoding="utf-8") as f:
                f.write(single_html)

        # 2. Czyszczenie i renderowanie podstron stałych miejsc
        places_dir.mkdir(parents=True, exist_ok=True)

        place_template = self.env.get_template("place_page.html")
        rendered_places = 0
        for place_id, place_data in places.items():
            upcoming = [ev for ev in events if ev.place_id == place_id or ev.analysis.ticket_info.place_id == place_id]
            
            p_folder = places_dir / place_id
            p_folder.mkdir(parents=True, exist_ok=True)
            p_file = p_folder / "index.html"

            p_html = place_template.render(
                city=city_name,
                city_tag=city_tag,
                place=place_data,
                upcoming_events=upcoming
            )
            with open(p_file, "w", encoding="utf-8") as f:
                f.write(p_html)
            rendered_places += 1

        # 3. Renderowanie agendy miasta
        home_template = self.env.get_template("home.html")
        home_html = home_template.render(city=city_name, city_tag=city_tag, events=events)
        home_file = city_dir / "index.html"
        with open(home_file, "w", encoding="utf-8") as f:
            f.write(home_html)

        print(f"[RENDERER] {city_name}: Wygenerowano {len(events)} wydarzeń oraz {rendered_places} wizytówek miejsc.")

    def render_seo_files(self, output_dir: str = "public", base_url: str = "https://corobicw.pl") -> None:
        today_iso = datetime.now().strftime("%Y-%m-%d")
        out_path = Path(output_dir)
        
        urls: List[str] = []
        for root, _, files in os.walk(out_path):
            if "index.html" in files:
                rel = os.path.relpath(root, out_path)
                url_path = "" if rel == "." else rel.replace("\\", "/") + "/"
                urls.append(f"{base_url.rstrip('/')}/{url_path}")
        
        urls = sorted(set(urls))

        # 1. Generowanie sitemap.xml
        xml_entries = "\n".join([
            f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today_iso}</lastmod>\n  </url>"
            for u in urls
        ])
        sitemap_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{xml_entries}\n</urlset>'
        
        with open(out_path / "sitemap.xml", "w", encoding="utf-8") as f:
            f.write(sitemap_content)

        # 2. Generowanie robots.txt
        robots_content = f"User-agent: *\nAllow: /\n\nSitemap: {base_url.rstrip('/')}/sitemap.xml\n"
        with open(out_path / "robots.txt", "w", encoding="utf-8") as f:
            f.write(robots_content)

        print(f"[SEO] Wygenerowano sitemap.xml ({len(urls)} adresów) oraz robots.txt.")