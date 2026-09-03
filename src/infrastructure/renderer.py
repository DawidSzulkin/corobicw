import json
import os
import re
import shutil
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader
from src.core.models import FullEventPage

CITY_NAMES = {
    "kedzierzyn_kozle": "Kędzierzyn-Koźle",
    "opole": "Opole",
    "bielsko_biala": "Bielsko-Biała"
}

def _resolve_strict_city_name(tag: str) -> str:
    if not tag:
        return ""
    norm = str(tag).lower().replace("-", "_")
    return CITY_NAMES.get(norm, str(tag).title().replace("_", "-"))

def resolve_canonical_city(tag: str) -> str:
    return _resolve_strict_city_name(tag)

META_LABELS = [
    "Autor", "Autorka", "Autorzy", "Przekład", "Tłumaczenie",
    "Reżyseria", "Scenografia", "Kostiumy", "Muzyka", "Światło",
    "Choreografia", "Asystentka reżysera", "Asystent reżysera",
    "Kierownictwo muzyczne", "Produkcja", "Kierownik produkcji",
    "Obsada", "Występują", "Wykonawcy", "Artyści", "Prowadzenie",
    "Wydarzenie poprowadzi", "Sponsorem wydarzenia jest",
    "Informacje praktyczne", "Czas trwania", "Bramy", "Start", "Bilety"
]

RE_BR = re.compile(r'<br\s*/?>', re.IGNORECASE)
RE_SPACES = re.compile(r'[ \u202f\u200b]+')
RE_EMOJI = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27ff]+')
RE_PUNCT = re.compile(r'[\.!\?\n]')
RE_DOUBLE_DOT = re.compile(r'\s*\.\s*\.')
RE_MULTI_SPACE = re.compile(r'[ ]{2,}')
RE_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+')
RE_PS = re.compile(r'(?<!\n)\s*(P\.S\..*)$', re.IGNORECASE)

META_LABEL_PATTERNS = [
    (re.compile(r'(?<!\n)\b' + re.escape(lbl) + r'\s*:', re.IGNORECASE), f'\n\n* **{lbl}:**')
    for lbl in META_LABELS
]

def _process_event_description_to_html(ev: Any) -> str:
    raw_desc = ""
    analysis = getattr(ev, 'analysis', None) or (ev.get('analysis') if isinstance(ev, dict) else None)
    if analysis:
        raw_desc = getattr(analysis, 'full_description', '') or (analysis.get('full_description', '') if isinstance(analysis, dict) else '')
    if not raw_desc:
        raw_desc = getattr(ev, 'description', '') or (ev.get('description', '') if isinstance(ev, dict) else '')

    if not raw_desc or len(str(raw_desc).strip()) < 5:
        return "<p>Brak szczegółowego opisu wydarzenia.</p>"

    t = str(raw_desc).replace("\r", " ").replace("\t", " ")
    t = RE_BR.sub('\n', t)
    t = RE_SPACES.sub(' ', t)

    # Usuwanie spamu SEO
    target = "więcej informacji"
    while target in t.lower():
        pos = t.lower().find(target)
        start_search = max(0, pos - 250)
        prefix = t[start_search:pos]
        emoji_matches = list(RE_EMOJI.finditer(prefix))
        punc_matches = list(RE_PUNCT.finditer(prefix))
        if emoji_matches:
            cut_start = start_search + emoji_matches[-1].start()
        elif punc_matches:
            cut_start = start_search + punc_matches[-1].end()
        else:
            cut_start = max(0, pos - 60)
        t = t[:cut_start].rstrip(" .-\t") + ". " + t[pos + len(target):].lstrip(" .-\t")

    for pattern, repl in META_LABEL_PATTERNS:
        t = pattern.sub(repl, t)

    t = RE_PS.sub(r'\n\n\1', t)
    t = RE_DOUBLE_DOT.sub('.', t)
    t = RE_MULTI_SPACE.sub(' ', t)

    raw_blocks = [b.strip() for b in t.split("\n") if b.strip()]
    final_paragraphs = []
    for block in raw_blocks:
        if block.startswith("*") or block.startswith("-"):
            final_paragraphs.append(block)
            continue
        sentences = [s.strip() for s in RE_SENTENCE_SPLIT.split(block) if s.strip()]
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

class HTMLRenderer:
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir), auto_reload=False)
        self._assets_synced = False

    def _sync_assets(self, output_dir: str):
        if self._assets_synced:
            return
        out_assets = Path(output_dir) / "assets"
        src_assets = Path("assets") if Path("assets").exists() else Path("docs/assets")
        if src_assets.exists():
            out_assets.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_assets, out_assets, dirs_exist_ok=True)
        self._assets_synced = True

    def render_portal_hub(self, active_cities: List[Dict[str, str]], output_dir: str = "public"):
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        self._sync_assets(output_dir)

        template = self.env.get_template("portal_hub.html")
        html_out = template.render(cities=active_cities)

        hub_file = out_path / "index.html"
        hub_file.write_text(html_out, encoding="utf-8")
        print(f"[RENDERER] Strona główna portalu: {hub_file}")

    def render_city(
        self,
        city_name: str,
        city_tag: str,
        events: List[FullEventPage],
        places: Dict[str, Dict[str, Any]],
        output_dir: str = "public"
    ):
        city_dir = Path(output_dir) / city_tag
        events_dir = city_dir / "wydarzenia"
        places_dir = city_dir / "miejsca"

        self._sync_assets(output_dir)

        # 1. Czyszczenie i przygotowanie katalogu wydarzeń
        if events_dir.exists():
            shutil.rmtree(events_dir)
        events_dir.mkdir(parents=True, exist_ok=True)

        strict_city = _resolve_strict_city_name(city_tag)
        event_template = self.env.get_template("event_page.html")

        def _write_single_event(ev: FullEventPage):
            single_folder = events_dir / ev.slug
            single_folder.mkdir(parents=True, exist_ok=True)
            
            p_id = getattr(ev, 'place_id', None) or (ev.get('place_id') if isinstance(ev, dict) else None)
            if not p_id:
                an_data = getattr(ev, 'analysis', None) or (ev.get('analysis') if isinstance(ev, dict) else None)
                if an_data:
                    t_inf = getattr(an_data, 'ticket_info', None) or (an_data.get('ticket_info') if isinstance(an_data, dict) else None)
                    if t_inf:
                        p_id = getattr(t_inf, 'place_id', None) or (t_inf.get('place_id') if isinstance(t_inf, dict) else None)
            
            place_obj = places.get(p_id) if p_id else None
            desc_html = _process_event_description_to_html(ev)

            single_html = event_template.render(
                formatted_description=desc_html,
                ev=ev,
                event=ev,
                place=place_obj,
                city=strict_city,
                city_name=strict_city,
                city_tag=city_tag
            )
            (single_folder / "index.html").write_text(single_html, encoding="utf-8")

        # Równoległy zapis podstron wydarzeń (Thread Pool)
        with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) * 2)) as executor:
            list(executor.map(_write_single_event, events))

        # 2. Preindeksacja powiązań wydarzeń do miejsc w O(N) zamiast zagnieżdżonego O(M * N)
        events_by_place: Dict[str, List[FullEventPage]] = {}
        for ev in events:
            ev_pid = getattr(ev, 'place_id', None)
            if not ev_pid:
                an = getattr(ev, 'analysis', None)
                t_inf = getattr(an, 'ticket_info', None) if an else None
                ev_pid = getattr(t_inf, 'place_id', None) if t_inf else None
            if ev_pid:
                events_by_place.setdefault(str(ev_pid), []).append(ev)

        places_dir.mkdir(parents=True, exist_ok=True)

        premium_venues = set()
        cfg_file = Path("config") / f"{city_tag}.yaml"
        if cfg_file.exists():
            import yaml
            try:
                with open(cfg_file, "r", encoding="utf-8") as yf:
                    city_data = yaml.safe_load(yf) or {}
                    premium_venues = set(city_data.get("premium_venues", []))
            except Exception:
                pass

        place_template = self.env.get_template("place_page.html")
        rendered_places = 0

        def _write_single_place(item):
            place_id, place_data = item
            upcoming = events_by_place.get(str(place_id), [])
            is_premium = place_id in premium_venues or place_data.get("group") in ["kultura", "theatre"]
            if not upcoming and not is_premium:
                return False

            p_folder = places_dir / str(place_id)
            p_folder.mkdir(parents=True, exist_ok=True)

            p_html = place_template.render(
                place=place_data,
                upcoming_events=upcoming,
                city=strict_city,
                city_name=strict_city,
                city_tag=city_tag
            )
            (p_folder / "index.html").write_text(p_html, encoding="utf-8")
            return True

        with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) * 2)) as executor:
            results = list(executor.map(_write_single_place, places.items()))
            rendered_places = sum(1 for r in results if r)

        # 3. Renderowanie agendy głównej miasta
        home_template = self.env.get_template("home.html")
        home_html = home_template.render(
            events=events,
            city=strict_city,
            city_name=strict_city,
            city_tag=city_tag
        )
        (city_dir / "index.html").write_text(home_html, encoding="utf-8")

        print(f"[RENDERER] {city_name}: Wygenerowano {len(events)} podstron wydarzeń i {rendered_places} wizytówek miejsc.")

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

        xml_entries = "\n".join([
            f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today_iso}</lastmod>\n  </url>"
            for u in urls
        ])
        sitemap_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{xml_entries}\n</urlset>'
        (out_path / "sitemap.xml").write_text(sitemap_content, encoding="utf-8")

        robots_content = f"User-agent: *\nAllow: /\n\nSitemap: {base_url.rstrip('/')}/sitemap.xml\n"
        (out_path / "robots.txt").write_text(robots_content, encoding="utf-8")

        print(f"[SEO] Wygenerowano sitemap.xml ({len(urls)} adresów) oraz robots.txt.")