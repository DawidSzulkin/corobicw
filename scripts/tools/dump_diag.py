from pathlib import Path

out_lines = []

def log(msg=""):
    out_lines.append(str(msg))

log("="*70)
log("1. KUPBILECIK_PL.PY (KOMPLETNY KOD)")
log("="*70)
kb = Path("src/infrastructure/scrapers/national/kupbilecik_pl.py")
if kb.exists():
    log(kb.read_text(encoding="utf-8-sig", errors="replace"))
else:
    log("[!] Brak pliku kupbilecik_pl.py")

log("\n" + "="*70)
log("2. BILETYNA_PL.PY (KOMPLETNY KOD)")
log("="*70)
bil = Path("src/infrastructure/scrapers/national/biletyna_pl.py")
if bil.exists():
    log(bil.read_text(encoding="utf-8-sig", errors="replace"))
else:
    log("[!] Brak pliku biletyna_pl.py")

log("\n" + "="*70)
log("3. FRAGMENTY KODU Z LOGIKĄ MIEJSC (PLACE_ID / VENUE / MATCHER)")
log("="*70)
for py_file in Path("src").rglob("*.py"):
    try:
        txt = py_file.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue
    if any(term in txt for term in ["places_clean", "places_dict", "place_resolver", "match_venue", "ticket_info"]):
        log(f"\n>>> PLIK: {py_file}")
        lines = txt.splitlines()
        for idx, line in enumerate(lines, 1):
            if any(k in line.lower() for k in ["places_clean", "place_id", "fuzzy", "ratio", "similarity", "venue_name"]):
                start = max(0, idx - 2)
                end = min(len(lines), idx + 3)
                log(f"--- Linia {idx} ---")
                log("\n".join(lines[start:end]))

Path("debug_dump.txt").write_text("\n".join(out_lines), encoding="utf-8")
print("[OK] Zrzut zapisany do debug_dump.txt")
