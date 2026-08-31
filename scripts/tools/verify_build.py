from pathlib import Path
from bs4 import BeautifulSoup
import sys

PUBLIC_DIR = Path("public")
if not PUBLIC_DIR.exists():
    print("[!] Katalog public/ nie istnieje!")
    sys.exit(1)

print("\n" + "="*70)
print(" AUDYT INTEGRALNOŚCI STRONY PO BUDOWIE (HTML / CSS / ASSETS)")
print("="*70)

cities = [d.name for d in PUBLIC_DIR.iterdir() if d.is_dir() and d.name not in ["assets", "css", "js"]]
total_pages = 0
errors = []
warnings = []

for city in cities:
    city_dir = PUBLIC_DIR / city
    events_dir = city_dir / "wydarzenia"
    places_dir = city_dir / "miejsca"
    
    # 1. Kontrola strony głównej miasta
    city_index = city_dir / "index.html"
    if not city_index.exists():
        errors.append(f"[{city.upper()}] Brak pliku index.html miasta!")
    else:
        total_pages += 1
        soup = BeautifulSoup(city_index.read_text(encoding="utf-8"), "html.parser")
        if not soup.find("h1"):
            errors.append(f"[{city.upper()}] index.html nie zawiera tagu <h1>")
        if not soup.find_all("link", rel="stylesheet"):
            warnings.append(f"[{city.upper()}] index.html nie linkuje żadnego arkusza CSS!")
            
    # 2. Kontrola podstron wydarzeń
    if events_dir.exists():
        ev_subdirs = [d for d in events_dir.iterdir() if d.is_dir()]
        print(f" -> {city.upper()}: Znaleziono {len(ev_subdirs)} wygenerowanych wydarzeń")
        
        for ev_d in ev_subdirs:
            ev_html = ev_d / "index.html"
            if not ev_html.exists():
                errors.append(f"[BRAK INDEX] Folder {ev_d.name} nie zawiera index.html")
                continue
                
            total_pages += 1
            content = ev_html.read_text(encoding="utf-8")
            
            # Weryfikacja podstawowych znaczników
            if len(content) < 300:
                errors.append(f"[PUSTA STRONA] {ev_d.name} ma mniej niż 300 bajtów.")
            if "undefined" in content or "None" in content[:400]:
                warnings.append(f"[WYCIEK NULL/NONE] Podstrona {ev_d.name} zawiera tekst 'None' lub 'undefined'")
                
    # 3. Kontrola wizytówek miejsc
    if places_dir.exists():
        pl_subdirs = [d for d in places_dir.iterdir() if d.is_dir()]
        print(f" -> {city.upper()}: Znaleziono {len(pl_subdirs)} wizytówek miejsc")
        total_pages += len(pl_subdirs)

print(f"\nŁącznie zindeksowano podstron: {total_pages}")

if errors:
    print(f"\n[!] BŁĘDY KRYTYCZNE ({len(errors)}):")
    for err in errors[:10]:
        print(f"   * {err}")
else:
    print("\n[OK] Brak błędów krytycznych w strukturze HTML.")

if warnings:
    print(f"\n[?] OSTRZEŻENIA / DROBNE ANOMALIE ({len(warnings)}):")
    for w in warnings[:10]:
        print(f"   * {w}")
else:
    print("[OK] Brak anomalii w treści podstron.")

print("="*70 + "\n")
