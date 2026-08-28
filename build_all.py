import yaml
from pathlib import Path
from src.pipeline import run_city_pipeline
from src.renderer import HTMLRenderer

def main():
    renderer = HTMLRenderer(template_dir="templates")
    config_dir = Path("config")
    
    city_configs = [
        config_dir / "kedzierzyn_kozle.yaml",
        config_dir / "bielsko_biala.yaml"
    ]

    active_cities_hub = []

    for cfg_path in city_configs:
        if not cfg_path.exists():
            continue
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            
        city_tag = cfg.get("city_tag", "")
        city_name = cfg.get("city", "")
        
        # Renderowanie agendy i podstron wydarzeń
        run_city_pipeline(cfg, renderer, output_dir="public", render_only=True)
        active_cities_hub.append({"name": city_name, "tag": city_tag})

    # Renderowanie głównej strony portalu z wyborem miast
    renderer.render_portal_hub(active_cities=active_cities_hub, output_dir="public")

    # Automatyczne generowanie sitemap.xml oraz robots.txt
    renderer.render_seo_files(output_dir="public", base_url="https://corobicw.pl")

    print("\n[SUKCES] Portal wygenerowany kompletnie dla wszystkich miast.")

if __name__ == "__main__":
    main()