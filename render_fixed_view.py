import sys
import json
import sqlite3
import re
from urllib.parse import urlparse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

root = Path.cwd().resolve()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from src.domain.pipeline import _load_places_index, _prepare_event_models
from src.core.models import TicketOffer

# 1. Pobranie rekordu z bazy
db_path = root / "data" / "events.db"
raw_event = None
with sqlite3.connect(db_path) as conn:
    c = conn.cursor()
    c.execute("SELECT payload FROM events WHERE city_tag = 'bielsko_biala' AND (title LIKE '%depresja%' OR title LIKE '%Depresja%') LIMIT 1")
    row = c.fetchone()
    if row:
        raw_event = json.loads(row[0])

if not raw_event:
    print("[BŁĄD] Nie znaleziono wydarzenia w bazie.")
    sys.exit(1)

# 2. Inteligentne czyszczenie i deduplikacja ofert per PROVIDER
def sanitize_price(price_str: str, provider: str) -> str:
    if not price_str:
        return "Sprawdź dostępność"
    p = price_str.strip()
    # Usunięcie dopisków w nawiasach typu (KupBilecik), (BCK Bilety)
    p = re.sub(r"\s*\([^)]*\)", "", p).strip()
    if p.lower() in ["bilety płatne", "płatne", "bilet", "kup bilet"]:
        return "Sprawdź dostępność"
    return p

def extract_numeric_price(p_str: str) -> float:
    match = re.search(r"(\d+(?:[.,]\d+)?)", p_str.replace(" ", ""))
    if match:
        return float(match.group(1).replace(",", "."))
    return float("inf")

def clean_url(u: str) -> str:
    if not u: return ""
    p = urlparse(u.strip())
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")

raw_offers = raw_event.get("ticket_offers", [])
grouped_offers = {}

for off in raw_offers:
    prov = off.get("provider", "Inne").strip()
    url = clean_url(off.get("url", ""))
    price = sanitize_price(off.get("price", ""), prov)
    
    # Jeśli dostawca już istnieje, wybieramy ofertę z lepszą informacją o cenie
    if prov not in grouped_offers:
        grouped_offers[prov] = {
            "provider": prov,
            "url": url,
            "price": price,
            "raw_price": off.get("price", "")
        }
    else:
        # Zastąp, jeśli nowa oferta ma konkretną cenę, a stara miała tylko 'Sprawdź dostępność'
        if grouped_offers[prov]["price"] == "Sprawdź dostępność" and price != "Sprawdź dostępność":
            grouped_offers[prov]["price"] = price
            grouped_offers[prov]["url"] = url

# Konwersja na listę
deduped_offers = list(grouped_offers.values())

# Sortowanie: oferty z ceną numeryczną na górę wg ceny, potem reszta
deduped_offers.sort(key=lambda x: extract_numeric_price(x["price"]))

# Przypisanie tagów na podstawie twardych danych
min_numeric = min([extract_numeric_price(o["price"]) for o in deduped_offers] or [float("inf")])

final_ticket_offers = []
for idx, o in enumerate(deduped_offers):
    tag = None
    tag_class = None
    u_low = o["url"].lower()
    prov_low = o["provider"].lower()
    
    num_p = extract_numeric_price(o["price"])
    if num_p < float("inf") and num_p == min_numeric and len(deduped_offers) > 1:
        tag = "Najlepsza cena"
        tag_class = "best-price"
    elif "bck" in u_low or "organizator" in prov_low or "bck" in prov_low:
        tag = "Oficjalna kasa"
        tag_class = "official"
        
    discounts = []
    if "bck" in u_low or "organizator" in prov_low:
        discounts = [
            {"name": "Bielska Karta Rodzina+", "val": "-50%"},
            {"name": "Bielska Karta Seniora", "val": "-50%"},
            {"name": "Weteran+", "val": "Bezpłatnie"}
        ]
        
    final_ticket_offers.append({
        "provider": o["provider"],
        "url": o["url"],
        "price": o["price"],
        "is_primary": (idx == 0),
        "tag": tag,
        "tag_class": tag_class,
        "discounts": discounts
    })

raw_event["ticket_offers"] = final_ticket_offers

# 3. Budowa modelu Pydantic
places_by_id = _load_places_index("bielsko_biala")
city_meta = {"city_tag": "bielsko_biala", "city": "Bielsko-Biała"}
event_models = _prepare_event_models([raw_event], city_meta, "Bielsko-Biała", places_by_id)
event_model = event_models[0]

# Podmiana ofert w obiekcie domenowym
event_model.ticket_offers = [TicketOffer(**o) for o in final_ticket_offers]

# 4. Zaktualizowany, dopracowany szablon HTML/CSS
template_content = '''<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ event.title }} | {{ city_name or city }} - CoRobićW</title>
  <style>
    :root {
      --bg: #09090b; --card-bg: #121215; --card-hover: #18181b; --text: #f4f4f5;
      --text-muted: #a1a1aa; --border: #27272a; --border-strong: #ffffff;
      --btn-primary-bg: #ffffff; --btn-primary-text: #000000;
      --accent-green: #10b981; --accent-blue: #38bdf8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.5; font-size: 15px; padding: 24px 16px;
    }
    .layout { max-width: 1080px; margin: 0 auto; display: grid; grid-template-columns: 1fr 340px; gap: 32px; }
    @media (max-width: 850px) { .layout { grid-template-columns: 1fr; } }
    
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 20px; }
    .card-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 800; color: var(--text-muted); border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 14px; }
    
    .info-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.9rem; }
    .info-label { color: var(--text-muted); text-transform: uppercase; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px; }
    .info-val { font-weight: 600; text-align: right; }

    /* SEKCJA BILETÓW - DOPRACOWANY CENEO STYLE */
    .ticket-section { margin-top: 20px; border-top: 1px solid var(--border); padding-top: 16px; }
    .ticket-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .ticket-header-title { font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); }
    .ticket-header-count { font-size: 0.75rem; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 10px; border: 1px solid var(--border); }

    .offers-list { display: flex; flex-direction: column; gap: 8px; }
    .offer-item {
      border: 1px solid var(--border); background: var(--card-hover); border-radius: 5px;
      overflow: hidden; transition: border-color 0.2s;
    }
    .offer-item:hover { border-color: rgba(255,255,255,0.25); }
    .offer-item.is-primary { border-color: rgba(255,255,255,0.35); background: rgba(255,255,255,0.02); }

    .offer-main {
      display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center;
      padding: 12px 14px;
    }
    .offer-details { display: flex; flex-direction: column; gap: 4px; }
    .offer-provider-row { display: flex; align-items: center; gap: 8px; }
    .offer-provider { font-size: 0.8rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text); }
    
    .offer-badge {
      font-size: 0.65rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;
      padding: 2px 6px; border-radius: 3px;
    }
    .offer-badge.best-price { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); }
    .offer-badge.official { background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); border: 1px solid rgba(56, 189, 248, 0.3); }

    .offer-price { font-size: 1.05rem; font-weight: 800; color: var(--text); letter-spacing: -0.3px; }
    .offer-price.text-mode { font-size: 0.85rem; font-weight: 600; color: var(--text-muted); }

    /* PRZYCISKI - HIERARCHIA WIZUALNA */
    .btn-buy {
      display: inline-flex; align-items: center; justify-content: center;
      text-decoration: none; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;
      padding: 8px 14px; border-radius: 4px; min-width: 90px; text-align: center;
      transition: all 0.15s ease;
    }
    .btn-buy.primary {
      background: var(--btn-primary-bg); color: var(--btn-primary-text); border: 1px solid var(--btn-primary-bg);
    }
    .btn-buy.primary:hover { background: #e4e4e7; border-color: #e4e4e7; transform: translateY(-1px); }
    
    .btn-buy.secondary {
      background: transparent; color: var(--text); border: 1px solid var(--border);
    }
    .btn-buy.secondary:hover { border-color: var(--text); background: rgba(255,255,255,0.05); }

    /* AKORDEON ZNIŻEK */
    .discounts-accordion { border-top: 1px dashed var(--border); background: rgba(56, 189, 248, 0.03); }
    .discounts-accordion summary {
      padding: 8px 14px; font-size: 0.72rem; font-weight: 700; color: var(--accent-blue);
      cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center;
      text-transform: uppercase; letter-spacing: 0.5px;
    }
    .discounts-accordion summary::-webkit-details-marker { display: none; }
    .discounts-accordion summary::after { content: "▼"; font-size: 0.6rem; opacity: 0.7; }
    .discounts-accordion[open] summary::after { transform: rotate(180deg); }
    
    .discounts-list { list-style: none; padding: 0 14px 10px; margin: 0; display: flex; flex-direction: column; gap: 5px; }
    .discounts-list li {
      display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);
      border-bottom: 1px solid rgba(255,255,255,0.03); padding-bottom: 3px;
    }
    .discounts-list li:last-child { border-bottom: none; }
    .discounts-list .disc-val { font-weight: 700; color: var(--accent-green); }

    h1 { font-size: 1.8rem; font-weight: 900; margin-bottom: 12px; line-height: 1.2; }
    .desc { font-size: 0.95rem; color: #d4d4d8; line-height: 1.6; }
    .desc p { margin-bottom: 12px; }
  </style>
</head>
<body>
  <div class="layout">
    <div class="main-column">
      <h1>{{ event.title }}</h1>
      <div class="desc">{{ formatted_description|safe }}</div>
    </div>

    <div class="sidebar-column">
      <div class="card">
        <div class="card-title">Bilety i Organizacja</div>
        <div class="info-row"><span class="info-label">Data</span><span class="info-val">{{ event.date_formatted }}</span></div>
        <div class="info-row"><span class="info-label">Start</span><span class="info-val">{{ event.analysis.ticket_info.time_start }}</span></div>
        <div class="info-row"><span class="info-label">Miejsce</span><span class="info-val">{{ event.analysis.ticket_info.venue_name }}</span></div>
        <div class="info-row"><span class="info-label">Parking</span><span class="info-val">{{ event.analysis.quick_facts.parking }}</span></div>

        <div class="ticket-section">
          <div class="ticket-header">
            <span class="ticket-header-title">Dostępne bilety</span>
            <span class="ticket-header-count">{{ event.ticket_offers|length }} opcje</span>
          </div>

          <div class="offers-list">
            {% for offer in event.ticket_offers %}
            <div class="offer-item {% if loop.first %}is-primary{% endif %}">
              <div class="offer-main">
                <div class="offer-details">
                  <div class="offer-provider-row">
                    <span class="offer-provider">{{ offer.provider }}</span>
                    {% if offer.tag %}
                    <span class="offer-badge {{ offer.tag_class }}">{{ offer.tag }}</span>
                    {% endif %}
                  </div>
                  <div class="offer-price {% if 'zł' not in offer.price %}text-mode{% endif %}">
                    {{ offer.price }}
                  </div>
                </div>

                <div class="offer-action">
                  <a href="{{ offer.url }}" target="_blank" rel="nofollow noopener" 
                     class="btn-buy {% if loop.first %}primary{% else %}secondary{% endif %}"
                     aria-label="Kup bilet w {{ offer.provider }}">
                    Kup bilet
                  </a>
                </div>
              </div>

              {% if offer.discounts and offer.discounts|length > 0 %}
              <details class="discounts-accordion">
                <summary>Zniżki miejskie ({{ offer.discounts|length }})</summary>
                <ul class="discounts-list">
                  {% for d in offer.discounts %}
                  <li><span>{{ d.name }}</span><span class="disc-val">{{ d.val }}</span></li>
                  {% endfor %}
                </ul>
              </details>
              {% endif %}
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>'''

desc = event_model.analysis.full_description if (event_model.analysis and event_model.analysis.full_description) else event_model.description
formatted_desc = "".join(f"<p>{p.strip()}</p>" for p in desc.split("\n\n") if p.strip())

template = Environment().from_string(template_content)
rendered = template.render(
    event=event_model,
    city_name="Bielsko-Biała",
    city_tag="bielsko_biala",
    formatted_description=formatted_desc
)

out_file = root / "test_depresja_komika.html"
out_file.write_text(rendered, encoding="utf-8")
print(f"[OK] Wygenerowano nowy, oczyszczony plik: {out_file.name}")