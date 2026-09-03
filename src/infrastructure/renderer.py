import json
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader
from src.core.models import FullEventPage

def _resolve_strict_city_name(tag: str) -> str:
    if not tag: return ""
    cmap = {"kedzierzyn_kozle": "Kędzierzyn-Koźle", "opole": "Opole", "bielsko_biala": "Bielsko-Biała"}
    return cmap.get(str(tag).lower(), str(tag).title().replace("_", "-"))

def _process_event_description_to_html(ev) -> str:
    # Ekstrakcja surowego opisu z modelu lub słownika
    raw_desc = ""
    analysis = getattr(ev, 'analysis', None) or (ev.get('analysis') if isinstance(ev, dict) else None)
    if analysis:
        raw_desc = getattr(analysis, 'full_description', '') or (analysis.get('full_description', '') if isinstance(analysis, dict) else '')
    if not raw_desc:
        raw_desc = getattr(ev, 'description', '') or (ev.get('description', '') if isinstance(ev, dict) else '')

    if not raw_desc or len(str(raw_desc).strip()) < 5:
        return "<p>Brak szczegółowego opisu wydarzenia.</p>"

    import re
    t = str(raw_desc).replace("\r", " ").replace("\t", " ")
    t = re.sub(r'<br\s*/?>', '\n', t, flags=re.IGNORECASE)
    t = re.sub(r'[ \u202f\u200b]', ' ', t)

    # 1. Usuwanie spamu SEO (- więcej informacji)
    target = "więcej informacji"
    while target in t.lower():
        pos = t.lower().find(target)
        start_search = max(0, pos - 250)
        prefix = t[start_search:pos]
        emoji_matches = list(re.finditer(r'[\U00010000-\U0010ffff\u2600-\u27ff]+', prefix))
        punc_matches = list(re.finditer(r'[\.!\?\n]', prefix))
        if emoji_matches:
            cut_start = start_search + emoji_matches[-1].start()
        elif punc_matches:
            cut_start = start_search + punc_matches[-1].end()
        else:
            cut_start = max(0, pos - 60)
        t = t[:cut_start].rstrip(" .-\t") + ". " + t[pos + len(target):].lstrip(" .-\t")

    # 2. Standaryzacja etykiet
    META_LABELS = [
        "Autor", "Autorka", "Autorzy", "Przekład", "Tłumaczenie",
        "Reżyseria", "Scenografia", "Kostiumy", "Muzyka", "Światło",
        "Choreografia", "Asystentka reżysera", "Asystent reżysera",
        "Kierownictwo muzyczne", "Produkcja", "Kierownik produkcji",
        "Obsada", "Występują", "Wykonawcy", "Artyści", "Prowadzenie",
        "Wydarzenie poprowadzi", "Sponsorem wydarzenia jest",
        "Informacje praktyczne", "Czas trwania", "Bramy", "Start", "Bilety"
    ]
    for lbl in META_LABELS:
        t = re.sub(r'(?<!\n)\b' + re.escape(lbl) + r'\s*:', f'\n\n* **{lbl}:**', t)

    t = re.sub(r'(?<!\n)\s*(P\.S\..*)$', r'\n\n\1', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\.\s*\.', '.', t)
    t = re.sub(r'[ ]{2,}', ' ', t)

    # 3. Podział narracji na akapity (~160-240 znaków)
    raw_blocks = [b.strip() for b in t.split("\n") if b.strip()]
    final_paragraphs = []
    for block in raw_blocks:
        if block.startswith("*") or block.startswith("-"):
            final_paragraphs.append(block)
            continue
        sentences = [s.strip() for s in re.split(r'(?<=[.!?…])\s+', block) if s.strip()]
        curr_buf, curr_len = [], 0
        for s in sentences:
            if s.upper().startswith("P.S.") or s.upper().startswith("UWAGA"):
                if curr_buf:
                    final_paragraphs.append(" ".join(curr_buf))
                    curr_buf, curr_len = [], 0
                final_paragraphs.append(s)
                continue
            curr_buf.append(s)
            curr_len += len(s)
            if curr_len >= 160:
                final_paragraphs.append(" ".join(curr_buf))
                curr_buf, curr_len = [], 0
        if curr_buf:
            final_paragraphs.append(" ".join(curr_buf))

    # 4. Generowanie semantycznego HTML
    html_parts = []
    for p in final_paragraphs:
        if p.startswith("* **"):
            item = re.sub(r'^\*\s*\*\*([^\*]+)\*\*(.*)$', r'<li><strong>\1</strong>\2</li>', p)
            html_parts.append(f'<ul class="desc-meta">{item}</ul>')
        elif p.startswith("* ") or p.startswith("- "):
            item = re.sub(r'^[\*\-]\s*(.*)$', r'<li>\1</li>', p)
            html_parts.append(f'<ul class="desc-list">{item}</ul>')
        elif p.upper().startswith("P.S."):
            html_parts.append(f'<p class="desc-ps"><em>{p}</em></p>')
        else:
            html_parts.append(f'<p>{p}</p>')

    res = "\n".join(html_parts)
    res = re.sub(r'</ul>\s*<ul class="desc-meta">', '', res)
    res = re.sub(r'</ul>\s*<ul class="desc-list">', '', res)
    return res



def _extract_raw_description(obj) -> str:
    """Wyczerpująca ekstrakcja surowego opisu z obiektu/słownika dowolnego typu."""
    if not obj:
        return ""
    
    # Próba 1: analysis.full_description (obiekt)
    analysis = getattr(obj, "analysis", None)
    if analysis:
        if hasattr(analysis, "full_description") and analysis.full_description:
            return str(analysis.full_description)
        if isinstance(analysis, dict) and analysis.get("full_description"):
            return str(analysis["full_description"])
        if isinstance(analysis, str):
            try:
                import json
                a_dict = json.loads(analysis)
                if isinstance(a_dict, dict) and a_dict.get("full_description"):
                    return str(a_dict["full_description"])
            except Exception:
                pass

    # Próba 2: direct description attribute / key
    if hasattr(obj, "description") and obj.description:
        return str(obj.description)
    if isinstance(obj, dict):
        if obj.get("description"):
            return str(obj["description"])
        if obj.get("raw_description"):
            return str(obj["raw_description"])
        if obj.get("full_description"):
            return str(obj["full_description"])
        # Zagnieżdżony słownik analysis
        if isinstance(obj.get("analysis"), dict):
            if obj["analysis"].get("full_description"):
                return str(obj["analysis"]["full_description"])
            if obj["analysis"].get("description"):
                return str(obj["analysis"]["description"])

    # Próba 3: raw_data JSON
    raw_data = getattr(obj, "raw_data", None) or (obj.get("raw_data") if isinstance(obj, dict) else None)
    if raw_data:
        if isinstance(raw_data, str):
            try:
                import json
                r_dict = json.loads(raw_data)
                if isinstance(r_dict, dict) and r_dict.get("description"):
                    return str(r_dict["description"])
            except Exception:
                pass
        elif isinstance(raw_data, dict) and raw_data.get("description"):
            return str(raw_data["description"])

    return ""


def resolve_canonical_city(tag: str) -> str:
    if not tag:
        return ""
    return CITY_CANONICAL_MAP.get(str(tag).lower(), str(tag).title().replace("_", "-"))


class HTMLRenderer:

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
            
            p_id = getattr(ev, 'place_id', None) or (ev.get('place_id') if isinstance(ev, dict) else None)
            if not p_id:
                an_data = getattr(ev, 'analysis', None) or (ev.get('analysis') if isinstance(ev, dict) else None)
                if an_data:
                    t_inf = getattr(an_data, 'ticket_info', None) or (an_data.get('ticket_info') if isinstance(an_data, dict) else None)
                    if t_inf:
                        p_id = getattr(t_inf, 'place_id', None) or (t_inf.get('place_id') if isinstance(t_inf, dict) else None)
            place_obj = places.get(p_id) if p_id else None
            
            single_html = event_template.render(
                formatted_description=_process_event_description_to_html(ev),

                ev=ev,
                event=ev,
                place=place_obj,
                city=_resolve_strict_city_name(city_tag
            ),
                city_name=_resolve_strict_city_name(city_tag),
                city_tag=city_tag
            )
            with open(single_file, "w", encoding="utf-8") as f:
                f.write(single_html)

        # 2. Czyszczenie i renderowanie podstron stałych miejsc
        places_dir.mkdir(parents=True, exist_ok=True)

        # Pobranie konfiguracji premium venues
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
            upcoming = []
            for ev in events:
                ev_pid = getattr(ev, 'place_id', None)
                analysis_pid = getattr(getattr(ev, 'analysis', None), 'ticket_info', None)
                analysis_pid_val = getattr(analysis_pid, 'place_id', None) if analysis_pid else None
                if ev_pid == place_id or analysis_pid_val == place_id:
                    upcoming.append(ev)
            
            is_premium = place_id in premium_venues or place_data.get("group") in ["kultura", "theatre"]
            if not upcoming and not is_premium:
                continue
            
            p_folder = places_dir / place_id
            p_folder.mkdir(parents=True, exist_ok=True)
            p_file = p_folder / "index.html"

            p_html = place_template.render(
                place=place_data,
                upcoming_events=upcoming,
                city=_resolve_strict_city_name(city_tag),
                city_name=_resolve_strict_city_name(city_tag),
                city_tag=city_tag
            )
            with open(p_file, "w", encoding="utf-8") as f:
                f.write(p_html)
            rendered_places += 1

        # 3. Renderowanie agendy miasta
        home_template = self.env.get_template("home.html")
        home_html = home_template.render(
            events=events,
            city=_resolve_strict_city_name(city_tag),
            city_name=_resolve_strict_city_name(city_tag),
            city_tag=city_tag
        )
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

        # 1. Sitemap.xml
        xml_entries = "\n".join([
            f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today_iso}</lastmod>\n  </url>"
            for u in urls
        ])
        sitemap_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{xml_entries}\n</urlset>'
        
        with open(out_path / "sitemap.xml", "w", encoding="utf-8") as f:
            f.write(sitemap_content)

        # 2. Robots.txt
        robots_content = f"User-agent: *\nAllow: /\n\nSitemap: {base_url.rstrip('/')}/sitemap.xml\n"
        with open(out_path / "robots.txt", "w", encoding="utf-8") as f:
            f.write(robots_content)

        print(f"[SEO] Wygenerowano sitemap.xml ({len(urls)} adresów) oraz robots.txt.")