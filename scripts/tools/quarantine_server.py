import json
import os
import re
import sqlite3
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List
import requests
import yaml

DB_PATH = Path("data/events.db")
BASE_DIR = Path(".").resolve()

def load_places(city_tag: str) -> Dict[str, Any]:
    norm_tag = city_tag.replace("-", "_")
    p_file = BASE_DIR / "data" / norm_tag / "places_clean.json"
    if not p_file.exists():
        p_file = BASE_DIR / "places_clean.json"
    if p_file.exists():
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {item.get("place_id") or item.get("id"): item for item in data}
        except Exception:
            return {}
    return {}

def save_places(city_tag: str, places: Dict[str, Any]):
    norm_tag = city_tag.replace("-", "_")
    p_file = BASE_DIR / "data" / norm_tag / "places_clean.json"
    p_file.parent.mkdir(parents=True, exist_ok=True)
    with open(p_file, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

def get_unresolved_venues() -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        return []

    unresolved = {}
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT city_tag, payload FROM events")
        for city_tag, payload_json in cursor.fetchall():
            try:
                ev = json.loads(payload_json)
            except Exception:
                continue

            pid = ev.get("place_id") or (ev.get("analysis", {}).get("ticket_info", {}).get("place_id"))
            venue = ev.get("venue") or ev.get("analysis", {}).get("ticket_info", {}).get("venue_name") or ""
            venue = venue.strip()

            if not pid and venue and venue.lower() not in ["brak", "bielsko-biała", "kędzierzyn-koźle", "opole"]:
                key = (city_tag, venue)
                if key not in unresolved:
                    unresolved[key] = {
                        "city_tag": city_tag,
                        "venue": venue,
                        "count": 0,
                        "sample_url": ev.get("source_url") or "",
                        "raw_address": ev.get("address") or ev.get("analysis", {}).get("address") or ""
                    }
                unresolved[key]["count"] += 1
                if not unresolved[key]["raw_address"]:
                    unresolved[key]["raw_address"] = ev.get("address") or ev.get("analysis", {}).get("address") or ""

    results = []
    for item in unresolved.values():
        raw_addr = item["raw_address"]
        venue = item["venue"]
        c_tag = item["city_tag"]
        
        clean_street = raw_addr
        for strip_w in [venue, c_tag.replace("_", " "), "Bielsko-Biała", "Kędzierzyn-Koźle", "Opole"]:
            clean_street = re.sub(rf"(?i)\b{re.escape(strip_w)}\b", "", clean_street)
        clean_street = clean_street.strip(" ,-")

        item["detected_street"] = clean_street
        results.append(item)

    return sorted(results, key=lambda x: x["count"], reverse=True)

def geocode_osm(query: str):
    headers = {"User-Agent": "CoRobicW_Quarantine/2.0"}
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200 and resp.json():
            hit = resp.json()[0]
            return float(hit["lat"]), float(hit["lon"])
    except Exception:
        pass
    return 50.0, 19.0

class QuarantineHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        items = get_unresolved_venues()
        
        rows_html = ""
        for it in items:
            v_esc = it['venue'].replace('"', '&quot;')
            street_val = it['detected_street'].replace('"', '&quot;')
            url_link = f"<a href='{it['sample_url']}' target='_blank' style='color:#38bdf8; text-decoration:none;'>ZOBACZ ↗</a>" if it['sample_url'] else "—"
            
            rows_html += f"""
            <tr style="border-bottom: 1px solid #27272a;">
                <td style="padding: 16px 12px; font-weight:700; color:#a1a1aa;">
                    <span style="background:#27272a; color:#fff; padding:4px 8px; font-size:0.75rem; text-transform:uppercase;">{it['city_tag']}</span>
                    <div style="font-size:0.75rem; margin-top:4px;">{it['count']} wyd.</div>
                </td>
                <td style="padding: 16px 12px; font-size:1.05rem; font-weight:700; color:#fff;">{it['venue']}</td>
                <td style="padding: 16px 12px;">{url_link}</td>
                <td style="padding: 16px 12px;">
                    <form method="POST" action="/map" style="display:flex; gap:8px;">
                        <input type="hidden" name="city_tag" value="{it['city_tag']}">
                        <input type="hidden" name="venue" value="{v_esc}">
                        <input type="text" name="target_id" placeholder="Wklej Place ID z bazy..." style="background:#18181b; border:1px solid #3f3f46; color:#fff; padding:8px 12px; flex:1;">
                        <button type="submit" style="background:#fff; color:#000; font-weight:700; border:none; padding:8px 16px; cursor:pointer;">ZATWIERDŹ ID</button>
                    </form>
                </td>
                <td style="padding: 16px 12px;">
                    <form method="POST" action="/create" style="display:flex; flex-direction:column; gap:8px;">
                        <input type="hidden" name="city_tag" value="{it['city_tag']}">
                        <input type="text" name="name" autocomplete="off" value="{v_esc}" style="background:#18181b; border:1px solid #3f3f46; color:#fff; padding:8px 12px;">
                        <div style="display:flex; gap:8px;">
                            <input type="text" name="street" autocomplete="off" value="{street_val}" placeholder="Ulica i numer..." style="background:#18181b; border:1px solid #3f3f46; color:#fff; padding:8px 12px; flex:1;">
                            <button type="submit" style="background:#27272a; color:#fff; font-weight:700; border:1px solid #3f3f46; padding:8px 16px; cursor:pointer;">UTWÓRZ I POBIERZ GPS</button>
                        </div>
                    </form>
                </td>
            </tr>
            """

        if not rows_html:
            rows_html = "<tr><td colspan='5' style='padding:40px; text-align:center; color:#4ade80; font-size:1.2rem; font-weight:700;'>✓ Wszystkie obiekty są prawidłowo zmapowane!</td></tr>"

        html_doc = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title>Kwarantanna Obiektów PRO</title>
    <style>
        body {{ background: #09090b; color: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 40px; }}
        h1 {{ font-size: 1.8rem; font-weight: 900; letter-spacing: -0.5px; margin-bottom: 8px; text-transform: uppercase; }}
        p {{ color: #a1a1aa; margin-bottom: 24px; font-size: 0.95rem; }}
        table {{ width: 100%; border-collapse: collapse; background: #121215; border: 1px solid #27272a; }}
        th {{ text-align: left; padding: 12px; background: #18181b; border-bottom: 1px solid #27272a; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #a1a1aa; }}
    </style>
</head>
<body>
    <h1>KWARANTANNA OBIEKTÓW PRO</h1>
    <p>Brakujące obiekty. Adresy zostały automatycznie wyciągnięte ze scrapera. Kliknij przycisk, aby utworzyć obiekt i pobrać koordynaty GPS.</p>
    <table>
        <thead>
            <tr>
                <th style="width:120px;">Miasto</th>
                <th>Surowy tekst</th>
                <th style="width:90px;">Źródło</th>
                <th style="width:380px;">Opcja A: Zmapuj istniejące</th>
                <th style="width:460px;">Opcja B: Utwórz nowy obiekt</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_doc.encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body)

        city_tag = params.get("city_tag", [""])[0]

        if self.path == "/create":
            name = params.get("name", [""])[0].strip()
            street = params.get("street", [""])[0].strip()
            
            city_name = "Bielsko-Biała" if "bielsko" in city_tag else ("Opole" if "opole" in city_tag else "Kędzierzyn-Koźle")
            slug_base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            place_id = f"{city_tag[:2]}-{slug_base}"

            lat, lon = geocode_osm(f"{street}, {city_name}")

            places = load_places(city_tag)
            places[place_id] = {
                "place_id": place_id,
                "name": name,
                "category": "Kultura i Rozrywka",
                "address": {
                    "street": street,
                    "city": city_name
                },
                "geo": {"lat": lat, "lon": lon}
            }
            save_places(city_tag, places)

            # Aktualizacja SQLite
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, payload FROM events WHERE city_tag = ?", (city_tag,))
                for ev_id, p_json in cursor.fetchall():
                    ev = json.loads(p_json)
                    v = ev.get("venue") or ev.get("analysis", {}).get("ticket_info", {}).get("venue_name") or ""
                    v = v.strip()
                    if name.lower() in v.lower() or v.lower() in name.lower():
                        ev["place_id"] = place_id
                        if "analysis" not in ev: ev["analysis"] = {}
                        if "ticket_info" not in ev["analysis"]: ev["analysis"]["ticket_info"] = {}
                        ev["analysis"]["ticket_info"]["place_id"] = place_id
                        cursor.execute("UPDATE events SET payload = ? WHERE id = ?", (json.dumps(ev, ensure_ascii=False), ev_id))
                conn.commit()

        elif self.path == "/map":
            target_mapping = params.get("target_mapping", [""])[0].strip()
            match = re.search(r'^\[(.*?)\]', target_mapping)
            if not match:
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return
            target_id = match.group(1).strip()
            venue = params.get("venue", [""])[0].strip()
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, payload FROM events WHERE city_tag = ?", (city_tag,))
                for ev_id, p_json in cursor.fetchall():
                    ev = json.loads(p_json)
                    v = ev.get("venue") or ev.get("analysis", {}).get("ticket_info", {}).get("venue_name") or ""
                    v = v.strip()
                    if venue.lower() == v.lower():
                        ev["place_id"] = target_id
                        if "analysis" not in ev: ev["analysis"] = {}
                        if "ticket_info" not in ev["analysis"]: ev["analysis"]["ticket_info"] = {}
                        ev["analysis"]["ticket_info"]["place_id"] = target_id
                        cursor.execute("UPDATE events SET payload = ? WHERE id = ?", (json.dumps(ev, ensure_ascii=False), ev_id))
                conn.commit()

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8081), QuarantineHandler)
    print("Serwer kwarantanny aktywny: http://localhost:8081")
    server.serve_forever()
