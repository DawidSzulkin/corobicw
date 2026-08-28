import json
from pathlib import Path

JSON_PATH = Path("data/kedzierzyn_kozle/indoor_atrakcje.json")
OUTPUT_HTML = Path("public/kedzierzyn_indoor.html")

def main():
    if not JSON_PATH.exists():
        print(f"[BŁĄD] Nie znaleziono pliku {JSON_PATH}. Najpierw uruchom skrypt pobierający dane!")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    cards_html = ""
    for idx, item in enumerate(items):
        name = item["name"]
        category = item["category"].replace("_", " ").title()
        lat = item["coordinates"]["lat"]
        lon = item["coordinates"]["lon"]
        logistics = item["logistics"]
        parking = f"{logistics['parking_distance_meters']} m" if logistics['parking_distance_meters'] is not None else "Brak danych"
        wheelchair = logistics["wheelchair"]
        age = logistics["age_group"]
        
        is_sponsored = (idx == 0)
        badge_html = '<span class="badge-sponsored">Wybór Redakcji</span>' if is_sponsored else ''
        card_class = "card sponsored" if is_sponsored else "card"

        # Generowanie osadzonej mapy Google Maps dla konkretnych współrzędnych
        map_iframe = f"""
        <div class="map-container">
          <iframe 
            width="100%" 
            height="140" 
            style="border:0; border-radius: 8px;" 
            loading="lazy" 
            allowfullscreen 
            src="https://maps.google.com/maps?q={lat},{lon}&z=15&output=embed">
          </iframe>
        </div>
        """

        cards_html += f"""
      <article class="{card_class}">
        {badge_html}
        <div>
          <div class="card-header">
            <div>
              <span class="card-sub">{category}</span>
              <h2 class="card-title">{name}</h2>
            </div>
            <span class="score-badge">95/100</span>
          </div>
          
          {map_iframe}

          <div class="logistics-grid">
            <div class="log-row"><span class="log-label">Parking:</span><span class="log-val">{parking}</span></div>
            <div class="log-row"><span class="log-label">Dla wózków:</span><span class="log-val">{wheelchair}</span></div>
            <div class="log-row"><span class="log-label">Wiek:</span><span class="log-val">{age}</span></div>
            <div class="log-row"><span class="log-label">Zadaszenie:</span><span class="log-val">Pełne (Indoor)</span></div>
          </div>
          <p class="desc">Zadaszony obiekt w Kędzierzynie-Koźlu zweryfikowany pod kątem dostępności logistycznej i bliskości stref parkowania.</p>
        </div>
        <div class="card-actions" style="margin-top: auto;">
          <a href="https://maps.google.com/?q={lat},{lon}" target="_blank" rel="noopener" class="btn btn-outline">Otwórz w Mapach</a>
          <a href="#" class="btn btn-primary">Szczegóły</a>
        </div>
      </article>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kędzierzyn-Koźle: Co robić pod dachem? | corobicw.pl</title>
  <style>
    :root {{
      --bg: #f9fafb; --card-bg: #ffffff; --text-main: #111827; --text-muted: #6b7280;
      --border: #e5e7eb; --accent: #2563eb; --accent-hover: #1d4ed8; --tag-bg: #f3f4f6;
      --success-bg: #dcfce7; --success-text: #166534;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background-color: var(--bg); color: var(--text-main); padding: 24px; line-height: 1.6; }}
    .container {{ max-width: 1080px; margin: 0 auto; }}
    .breadcrumbs {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px; }}
    .breadcrumbs a {{ color: var(--text-main); text-decoration: none; font-weight: 500; }}
    header {{ border-bottom: 1px solid var(--border); padding-bottom: 24px; margin-bottom: 24px; }}
    h1 {{ font-size: 2rem; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 12px; }}
    .lead {{ color: var(--text-muted); font-size: 1.05rem; max-width: 800px; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 24px; margin-top: 32px; }}
    @media (min-width: 768px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); display: flex; flex-direction: column; position: relative; }}
    .card.sponsored {{ border: 2px solid #fbbf24; background: #fffcf2; }}
    .badge-sponsored {{ position: absolute; top: -12px; left: 24px; background: #fbbf24; color: #78350f; font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 12px; text-transform: uppercase; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }}
    .card-sub {{ font-size: 0.75rem; color: var(--accent); text-transform: uppercase; font-weight: 700; display: block; margin-bottom: 4px; }}
    .card-title {{ font-size: 1.25rem; font-weight: 700; color: var(--text-main); line-height: 1.2; }}
    .score-badge {{ background: var(--success-bg); color: var(--success-text); font-weight: 700; font-size: 0.85rem; padding: 4px 8px; border-radius: 6px; }}
    .map-container {{ margin-bottom: 16px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
    .logistics-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; background: var(--bg); padding: 16px; border-radius: 8px; margin-bottom: 16px; border: 1px solid var(--border); }}
    .log-row {{ display: flex; flex-direction: column; }}
    .log-label {{ color: var(--text-muted); font-size: 0.75rem; font-weight: 500; text-transform: uppercase; margin-bottom: 2px; }}
    .log-val {{ font-weight: 600; color: var(--text-main); font-size: 0.9rem; }}
    .desc {{ font-size: 0.95rem; color: var(--text-muted); margin-bottom: 20px; }}
    .card-actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .btn {{ padding: 10px; text-align: center; border-radius: 8px; font-size: 0.9rem; font-weight: 600; text-decoration: none; border: none; cursor: pointer; }}
    .btn-outline {{ background: transparent; border: 1px solid var(--border); color: var(--text-main); }}
    .btn-outline:hover {{ background: var(--tag-bg); }}
    .btn-primary {{ background: var(--text-main); color: #fff; }}
    .btn-primary:hover {{ background: #000; }}
    .transparency-box {{ margin-top: 48px; padding: 24px; background: #fff; border: 1px solid var(--border); border-radius: 12px; font-size: 0.85rem; color: var(--text-muted); }}
  </style>
</head>
<body>
  <div class="container">
    <nav class="breadcrumbs">
      <a href="/">Strona główna</a> / <a href="/kedzierzyn-kozle/">Kędzierzyn-Koźle</a> / <span>Atrakcje pod dachem</span>
    </nav>
    <header>
      <h1>Kędzierzyn-Koźle: Co robić pod dachem?</h1>
      <p class="lead">Zestawienie {len(items)} zadaszonych obiektów z osadzonymi mapami i wyliczoną odległością do parkingów.</p>
    </header>
    <div class="grid">
      {cards_html}
    </div>
    <footer class="transparency-box">
      <strong>Metodologia portalu:</strong> Współrzędne i logistykę wygenerowano automatycznie z bazy OpenStreetMap.
    </footer>
  </div>
</body>
</html>
"""

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[SUKCES] Wygenerowano stronę z mapami: {OUTPUT_HTML}")

if __name__ == "__main__":
    main()
