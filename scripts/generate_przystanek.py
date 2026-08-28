from pathlib import Path

OUTPUT_HTML = Path("public/przystanek_gory.html")

html_content = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Przystanek Góry (Szczyrk) | Logistyka Obiektu</title>
  <style>
    :root {
      --bg: #f9fafb; --card-bg: #ffffff; --text-main: #111827; --text-muted: #6b7280;
      --border: #e5e7eb; --accent: #2563eb; --accent-hover: #1d4ed8; --tag-bg: #f3f4f6;
      --success-bg: #dcfce7; --success-text: #166534;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: var(--bg); color: var(--text-main); padding: 24px; line-height: 1.6; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
    .container { max-width: 600px; width: 100%; }
    .card { background: var(--card-bg); border: 2px solid #fbbf24; border-radius: 16px; padding: 24px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08); display: flex; flex-direction: column; position: relative; background: #fffcf2; }
    .badge-sponsored { position: absolute; top: -12px; left: 24px; background: #fbbf24; color: #78350f; font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
    .card-sub { font-size: 0.75rem; color: var(--accent); text-transform: uppercase; font-weight: 700; display: block; margin-bottom: 4px; letter-spacing: 0.05em; }
    .card-title { font-size: 1.5rem; font-weight: 700; color: var(--text-main); line-height: 1.2; }
    .score-badge { background: var(--success-bg); color: var(--success-text); font-weight: 700; font-size: 0.85rem; padding: 4px 8px; border-radius: 6px; }
    .logistics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; background: var(--bg); padding: 16px; border-radius: 8px; margin: 16px 0; border: 1px solid var(--border); }
    .log-row { display: flex; flex-direction: column; }
    .log-label { color: var(--text-muted); font-size: 0.75rem; font-weight: 500; text-transform: uppercase; margin-bottom: 2px; }
    .log-val { font-weight: 600; color: var(--text-main); font-size: 0.9rem; }
    .desc { font-size: 0.95rem; color: var(--text-muted); margin-bottom: 20px; }
    .card-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: auto; }
    .btn { padding: 12px; text-align: center; border-radius: 8px; font-size: 0.9rem; font-weight: 600; text-decoration: none; border: none; cursor: pointer; transition: 0.2s; }
    .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-main); }
    .btn-outline:hover { background: var(--tag-bg); }
    .btn-primary { background: var(--text-main); color: #fff; }
    .btn-primary:hover { background: #000; }
  </style>
</head>
<body>
  <div class="container">
    <article class="card">
      <span class="badge-sponsored">Zweryfikowana Logistyka</span>
      <div>
        <div class="card-header">
          <div>
            <span class="card-sub">Nocleg & Górskie Apartamenty</span>
            <h1 class="card-title">Przystanek Góry (Szczyrk)</h1>
          </div>
          <span class="score-badge">98/100</span>
        </div>
        
        <div class="logistics-grid">
          <div class="log-row"><span class="log-label">Parking:</span><span class="log-val">Darmowy (Przy budynku)</span></div>
          <div class="log-row"><span class="log-label">Skibus / Przystanek:</span><span class="log-val">120m</span></div>
          <div class="log-row"><span class="log-label">Wyciąg (Gondola):</span><span class="log-val">950m</span></div>
          <div class="log-row"><span class="log-label">Dla wózków:</span><span class="log-val">Ograniczony (Schody)</span></div>
          <div class="log-row"><span class="log-label">Dla maluchów:</span><span class="log-val">Łóżeczka / Wanienki</span></div>
          <div class="log-row"><span class="log-label">Ogród / Teren:</span><span class="log-val">Prywatny / Bezpieczny</span></div>
        </div>
        
        <p class="desc">Brak opisu marketingowego. Obiekt przystosowany dla rodzin z dziećmi w odległości poniżej 1 km od głównej infrastruktury narciarskiej i szlaków pieszych.</p>
      </div>
      
      <div class="card-actions">
        <a href="https://maps.google.com/?q=Przystanek+Góry+Szczyrk" target="_blank" rel="noopener" class="btn btn-outline">Nawiguj (GPS)</a>
        <a href="#" class="btn btn-primary">Sprawdź Dostępność</a>
      </div>
    </article>
  </div>
</body>
</html>
"""

OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[SUKCES] Wygenerowano plik: {OUTPUT_HTML}")
