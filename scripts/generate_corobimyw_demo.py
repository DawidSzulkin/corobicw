from pathlib import Path

OUTPUT_HTML = Path("public/corobimyw_event_demo.html")

html_content = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Warsztaty Robotyki dla Dzieci (Sosnowiec) | CoRobimyW.pl</title>
  <meta name="description" content="Warsztaty z klockami LEGO i robotyką w Sosnowcu. Sprawdź parking, dojazd GTFS i zniżki KDR.">

  <!-- SCHEMA.ORG DLA GOOGLE: EVENT + LOCATION -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Weekendowe Warsztaty Młodego Inżyniera",
    "startDate": "2026-03-28T11:00:00+01:00",
    "endDate": "2026-03-28T13:30:00+01:00",
    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    "eventStatus": "https://schema.org/EventScheduled",
    "location": {
      "@type": "Place",
      "name": "LaserHouse & Strefa Edukacji Sosnowiec",
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
      }
    },
    "offers": {
      "@type": "Offer",
      "price": "45",
      "priceCurrency": "PLN",
      "availability": "https://schema.org/InStock",
      "url": "https://corobimyw.pl"
    },
    "typicalAgeRange": "5-12"
  }
  </script>

  <style>
    :root {
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --border-subtle: #f1f5f9;
      --coral: #ff385c;
      --coral-hover: #e00b41;
      --green-badge: #059669;
      --green-bg: #ecfdf5;
      --blue-badge: #0284c7;
      --blue-bg: #f0f9ff;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text-main); padding: 24px 16px; display: flex; justify-content: center; line-height: 1.5; }
    .wrapper { max-width: 760px; width: 100%; }

    /* Nagłówek serwisu */
    .brand-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }
    .brand-logo { font-size: 1.1rem; font-weight: 800; color: var(--coral); letter-spacing: -0.02em; text-decoration: none; }
    .brand-city { font-size: 0.85rem; font-weight: 600; color: var(--text-muted); }

    /* Live Telemetry Bar - Pigułka Airbnb */
    .live-bar {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 9999px;
      padding: 8px 18px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.82rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .live-left { display: flex; align-items: center; gap: 8px; font-weight: 500; }
    .live-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 0 3px rgba(34,197,94,0.2); }
    .weather-text { color: var(--text-muted); }

    /* Karta Główna */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 28px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.04);
      margin-bottom: 24px;
    }

    /* Tagi i Pigułki */
    .tag-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
    .pill {
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 4px 10px;
      border-radius: 9999px;
    }
    .pill-coral { background: #fff1f2; color: var(--coral); }
    .pill-green { background: var(--green-bg); color: var(--green-badge); }
    .pill-blue { background: var(--blue-bg); color: var(--blue-badge); }

    .event-title {
      font-size: 1.6rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.25;
      margin-bottom: 6px;
    }
    .event-location-sub {
      color: var(--text-muted);
      font-size: 0.95rem;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    /* Kluczowe fakty o wydarzeniu (Termin, Wiek, Koszt) */
    .event-facts-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      background: #f8fafc;
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 24px;
    }
    @media (max-width: 540px) { .event-facts-grid { grid-template-columns: 1fr; } }

    .fact-item { display: flex; flex-direction: column; }
    .fact-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700; }
    .fact-value { font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-top: 2px; }

    /* Matryca Logistyczna Miejsca */
    .section-title {
      font-size: 0.85rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 12px;
    }
    .logistics-table {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 24px;
    }
    @media (max-width: 540px) { .logistics-table { grid-template-columns: 1fr; } }

    .log-cell {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      background: #ffffff;
    }
    .log-title { font-size: 0.72rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }
    .log-data { font-size: 0.9rem; font-weight: 600; color: var(--text-main); margin-top: 2px; }
    .highlight { color: var(--coral); font-weight: 700; }

    /* Stopka akcji */
    .card-actions {
      display: flex;
      gap: 12px;
    }
    .btn {
      flex: 1;
      padding: 14px;
      border-radius: 12px;
      font-size: 0.9rem;
      font-weight: 700;
      text-align: center;
      text-decoration: none;
      cursor: pointer;
      transition: background 0.15s ease;
      border: none;
    }
    .btn-primary { background: var(--coral); color: #fff; }
    .btn-primary:hover { background: var(--coral-hover); }
    .btn-outline { background: #fff; border: 1px solid var(--border); color: var(--text-main); }
    .btn-outline:hover { background: #f8fafc; }
  </style>
</head>
<body>

<div class="wrapper">

  <!-- TOP BAR -->
  <header class="brand-header">
    <a href="https://corobimyw.pl" class="brand-logo">corobimyw.pl</a>
    <span class="brand-city">Sosnowiec / Śląsk</span>
  </header>

  <!-- LIVE METEO BAR (Działa w przeglądarce klienta) -->
  <aside class="live-bar">
    <div class="live-left">
      <span class="live-dot"></span>
      <span id="weather-status">Pobieranie aury dla Sosnowca...</span>
    </div>
    <span class="weather-text" id="air-status">Powietrze: Dobre</span>
  </aside>

  <!-- KARTA WYDARZENIA + LOGISTYKA -->
  <article class="card">
    
    <div class="tag-row">
      <span class="pill pill-coral">Wydarzenie dla Dzieci</span>
      <span class="pill pill-green">KDR: Aktywna (-20%)</span>
      <span class="pill pill-blue">Zadaszone 100%</span>
    </div>

    <h1 class="event-title">Weekendowe Warsztaty Młodego Inżyniera</h1>
    <div class="event-location-sub">
      <span>📍 LaserHouse Sosnowiec, ul. Wojska Polskiego 8</span>
    </div>

    <!-- SPECYFIKACJA WYDARZENIA -->
    <div class="event-facts-grid">
      <div class="fact-item">
        <span class="fact-label">Termin</span>
        <span class="fact-value">Sobota, 11:00 – 13:30</span>
      </div>
      <div class="fact-item">
        <span class="fact-label">Wiek uczestników</span>
        <span class="fact-value">5 – 12 lat</span>
      </div>
      <div class="fact-item">
        <span class="fact-label">Bilety / Wstęp</span>
        <span class="fact-value">45 zł / os. (KDR: 36 zł)</span>
      </div>
    </div>

    <!-- LOGISTYKA INFRASTRUKTURALNA (OSM / GTFS) -->
    <div class="section-title">Weryfikacja Logistyczna Miejsca</div>
    
    <div class="logistics-table">
      <div class="log-cell">
        <div class="log-title">Parking (OSM Geometry)</div>
        <div class="log-data">Darmowy • <span class="highlight">25m</span> od drzwi</div>
      </div>
      <div class="log-cell">
        <div class="log-title">Autobus / Tramwaj (GTFS)</div>
        <div class="log-data">Przystanek Dęblińska: <span class="highlight">110m</span></div>
      </div>
      <div class="log-cell">
        <div class="log-title">Wózki Dziecięce</div>
        <div class="log-data">Podjazd bezprogowy • Szeroka winda</div>
      </div>
      <div class="log-cell">
        <div class="log-title">Dla Niemowląt</div>
        <div class="log-data">Przewijak w toalecie rodzinnej</div>
      </div>
    </div>

    <!-- PRZYCISKI AKCJI -->
    <div class="card-actions">
      <a href="https://maps.google.com/?q=LaserHouse+Sosnowiec" target="_blank" rel="noopener" class="btn btn-outline">Wyznacz trasę GPS</a>
      <a href="https://corobimyw.pl" class="btn btn-primary">Zarezerwuj Miejsce</a>
    </div>

  </article>

</div>

<!-- SKRYPT LIVE: POBIERANIE POGODY Z OPEN-METEO PO STRONIE KLIENTA -->
<script>
  (async function() {
    const lat = 50.2862;
    const lon = 19.1041;
    try {
      const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`);
      const data = await res.json();
      if (data && data.current_weather) {
        const temp = Math.round(data.current_weather.temperature);
        const isRain = data.current_weather.weathercode > 50;
        const aura = isRain ? "Opady deszczu" : "Pogodnie";
        document.getElementById("weather-status").innerText = `Sosnowiec: ${temp}°C,${aura}`;
      }
    } catch (e) {
      document.getElementById("weather-status").innerText = "Sosnowiec: Warunki sprzyjające wyjściu";
    }
  })();
</script>

</body>
</html>
"""

OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[OK] Wygenerowano szablon CoRobimyW: {OUTPUT_HTML}")
