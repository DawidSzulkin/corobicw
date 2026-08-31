from pathlib import Path

OUTPUT_HTML = Path("public/ultimate_hub_demo.html")

html_content = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LaserHouse & Atrakcje Pod Dachem - Sosnowiec | Matryca Logistyczna</title>
  <meta name="description" content="Sprawdź dostępność parkingów, czas dojazdu GTFS, jakość powietrza i udogodnienia dla dzieci w LaserHouse Sosnowiec. Dane zaktualizowane na żywo.">

  <!-- DANE STRUKTURALNE DLA GOOGLE (JSON-LD) - KLUCZ DO INDEKSACJI PROGRAMMATIC SEO -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "AmusementPark",
    "name": "LaserHouse Sosnowiec",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "ul. Wojska Polskiego 8",
      "addressLocality": "Sosnowiec",
      "postalCode": "41-200",
      "addressCountry": "PL"
    },
    "geo": {
      "@type": "GeoCoordinates",
      "latitude": 50.2862,
      "longitude": 19.1041
    },
    "openingHoursSpecification": [
      {
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "opens": "10:00",
        "closes": "21:00"
      }
    ],
    "isAccessibleForFree": false,
    "publicAccess": true,
    "amenityFeature": [
      {"@type": "LocationFeatureSpecification", "name": "Przewijak niemowlęcy", "value": true},
      {"@type": "LocationFeatureSpecification", "name": "Dostęp dla wózków", "value": true},
      {"@type": "LocationFeatureSpecification", "name": "Darmowy parking", "value": true}
    ]
  }
  </script>

  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --badge-kdr: #ec4899;
      --badge-rain: #0284c7;
      --badge-aqi: #22c55e;
      --tag-bg: #0f172a;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 24px 16px; line-height: 1.5; display: flex; justify-content: center; }
    .container { max-width: 720px; width: 100%; }

    /* Pasek kontekstowy na żywo (Pogoda + GIOŚ + Kalendarz) */
    .live-telemetry {
      background: linear-gradient(90deg, #1e293b, #0f172a);
      border: 1px solid var(--surface-border);
      border-radius: 12px;
      padding: 12px 16px;
      margin-bottom: 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      font-size: 0.82rem;
    }
    .telemetry-item { display: flex; align-items: center; gap: 6px; }
    .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .dot-green { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
    .dot-blue { background: #38bdf8; box-shadow: 0 0 8px #38bdf8; }

    /* Nota analityczna GUS */
    .gus-insight {
      background: #1e1b4b;
      border-left: 4px solid #818cf8;
      padding: 10px 14px;
      border-radius: 4px 8px 8px 4px;
      font-size: 0.8rem;
      color: #c7d2fe;
      margin-bottom: 24px;
    }

    /* Karta główna (Utilitarian Card) */
    .card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 16px;
      padding: 24px;
      position: relative;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);
    }

    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 16px;
      gap: 12px;
    }
    .category-label {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .card-title {
      font-size: 1.4rem;
      font-weight: 700;
      color: #fff;
      margin-top: 2px;
    }
    .badges-wrapper { display: flex; gap: 8px; flex-wrap: wrap; }
    .badge {
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .badge-rain { background: #0369a1; color: #e0f2fe; }
    .badge-kdr { background: #831843; color: #fbcfe8; border: 1px solid #db2777; }

    /* Siatka metryk i faktów logistycznych */
    .grid-metrics {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin: 16px 0;
    }
    @media (max-width: 480px) { .grid-metrics { grid-template-columns: 1fr; } }

    .metric-box {
      background: var(--tag-bg);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 10px 12px;
    }
    .metric-label {
      font-size: 0.7rem;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 600;
      display: block;
      margin-bottom: 2px;
    }
    .metric-val {
      font-size: 0.9rem;
      font-weight: 600;
      color: #f1f5f9;
    }
    .val-highlight { color: #38bdf8; }

    /* Przyciski operacyjne */
    .card-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 20px;
    }
    .btn {
      padding: 12px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      text-align: center;
      text-decoration: none;
      cursor: pointer;
      transition: all 0.2s;
      border: 1px solid transparent;
    }
    .btn-secondary {
      background: transparent;
      border-color: var(--surface-border);
      color: #cbd5e1;
    }
    .btn-secondary:hover { background: #334155; color: #fff; }
    .btn-primary {
      background: #0284c7;
      color: #fff;
    }
    .btn-primary:hover { background: #0369a1; }
  </style>
</head>
<body>

<div class="container">

  <!-- 1. LIVE TELEMETRY WIDGET (Open-Meteo + GIOŚ + Kalendarz) -->
  <aside class="live-telemetry">
    <div class="telemetry-item">
      <span class="dot dot-blue"></span>
      <span>Sosnowiec: <strong>Deszcz (14°C)</strong> – Rekomendowane obiekty indoor</span>
    </div>
    <div class="telemetry-item">
      <span class="dot dot-green"></span>
      <span>Powietrze (GIOŚ): <strong>Bardzo Dobre (PM2.5: 8 µg/m³)</strong></span>
    </div>
  </aside>

  <!-- 2. GUS CONTEXT DATA -->
  <div class="gus-insight">
    <strong>Wskaźnik demograficzny GUS:</strong> Sosnowiec posiada zagęszczenie 112 dzieci (0-14 lat) / km². Wysokie obłożenie sal zabaw w weekendy i dni deszczowe.
  </div>

  <!-- 3. KARTA GŁÓWNA - UTILITARIAN CORE -->
  <article class="card">
    <div class="card-top">
      <div>
        <span class="category-label">Rozrywka Indoor • Laser Tag</span>
        <h1 class="card-title">LaserHouse Sosnowiec</h1>
      </div>
      <div class="badges-wrapper">
        <span class="badge badge-rain">100% Zadaszone</span>
        <span class="badge badge-kdr">KDR: Aktywna (-15%)</span>
      </div>
    </div>

    <!-- Twarda matryca logistyczna wyciągnięta ze źródeł otwartych -->
    <div class="grid-metrics">
      <div class="metric-box">
        <span class="metric-label">Parking (OSM Geometry)</span>
        <span class="metric-val">Darmowy • <span class="val-highlight">25 metrów</span> od wejścia</span>
      </div>
      <div class="metric-box">
        <span class="metric-label">Komunikacja miejska (GTFS)</span>
        <span class="metric-val">Przystanek Dęblińska: <span class="val-highlight">110 m</span> (Linie 26, 150)</span>
      </div>
      <div class="metric-box">
        <span class="metric-label">Wózki & Dostępność (OSM Tagi)</span>
        <span class="metric-val">Podjazd bezprogowy • Szerokie drzwi</span>
      </div>
      <div class="metric-box">
        <span class="metric-label">Infrastruktura niemowlęca</span>
        <span class="metric-val">Przewijak w toalecie damskiej</span>
      </div>
      <div class="metric-box">
        <span class="metric-label">Godziny otwarcia (OSM Node)</span>
        <span class="metric-val">Dziś: <span class="val-highlight">10:00 - 21:00</span></span>
      </div>
      <div class="metric-box">
        <span class="metric-label">Model opłat (OSM Fee)</span>
        <span class="metric-val">Biletowany • Płatność kartą / BLIK</span>
      </div>
    </div>

    <!-- Szybkie akcje użytkownika -->
    <div class="card-actions">
      <a href="https://maps.google.com/?q=LaserHouse+Sosnowiec" target="_blank" rel="noopener" class="btn btn-secondary">Wyznacz trasę (GPS)</a>
      <a href="https://www.laserhouse.pl/sosnowiec/" target="_blank" rel="noopener" class="btn btn-primary">Rezerwacja online</a>
    </div>
  </article>

</div>

</body>
</html>
"""

OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[OK] Wygenerowano prototyp: {OUTPUT_HTML}")

