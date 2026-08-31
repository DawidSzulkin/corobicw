import re
import json
import sqlite3
from pathlib import Path

# 1. NAPRAWA KUPBILECIK_PL.PY (PLAKATY)
kb_path = Path("src/infrastructure/scrapers/national/kupbilecik_pl.py")
if kb_path.exists():
    kb_code = kb_path.read_text(encoding="utf-8")
    
    old_img_block = """            image_url = ""
            img_el = soup.select_one("img[src*='/plakaty/'], img[src*='/zdjecia/']")
            if img_el:
                src = img_el.get("src") or img_el.get("data-src")
                if src: image_url = urljoin(self.base_url, src)"""
                
    new_img_block = """            image_url = ""
            og_img = soup.select_one("meta[property='og:image'], meta[name='twitter:image']")
            if og_img and og_img.get("content"):
                image_url = urljoin(self.base_url, og_img.get("content").strip())
            
            if not image_url:
                img_el = soup.select_one("img[src*='/plakaty/'], img[src*='/zdjecia/'], img[src*='/i/'], img[src*='/upload/'], .wyd-img img, .top-image img")
                if img_el:
                    src = img_el.get("src") or img_el.get("data-src")
                    if src: image_url = urljoin(self.base_url, src)"""
                    
    if old_img_block in kb_code:
        kb_code = kb_code.replace(old_img_block, new_img_block)
        kb_path.write_text(kb_code, encoding="utf-8")
        print("[OK] Naprawiono selektor zdjęć w kupbilecik_pl.py")

# 2. NAPRAWA PIPELINE.PY (MATCHER MIEJSC - ELIMINACJA SŁÓW GENERYCZNYCH)
pipe_path = Path("src/domain/pipeline.py")
if pipe_path.exists():
    pipe_code = pipe_path.read_text(encoding="utf-8")
    
    generic_definition = '''
GENERIC_VENUE_TERMS = {
    "miejsce", "sala", "klub", "centrum", "teatr", "kawiarnia", "restauracja",
    "pub", "park", "plac", "hala", "dom", "osrodek", "ośrodek", "scena",
    "galeria", "filharmonia", "kino", "studio", "foyer", "kameralna"
}
'''
    if "GENERIC_VENUE_TERMS" not in pipe_code:
        pipe_code = generic_definition + pipe_code

    # Zaostrzenie logiki podobieństwa
    old_sim = """    if p_distinct and all(t in q_set for t in p_distinct):
        matched_ratio = len(p_distinct) / max(len(p_tokens), 1)
        return 0.90 + (0.09 * matched_ratio)

    if q_distinct and all(t in p_set for t in q_distinct):
        matched_ratio = len(q_distinct) / max(len(p_distinct), 1)
        return 0.85 + (0.10 * matched_ratio)"""

    new_sim = """    # Odrzucenie słów generycznych z decydującego dopasowania
    p_meaningful = [t for t in p_distinct if t.lower() not in GENERIC_VENUE_TERMS and len(t) > 2]
    q_meaningful = [t for t in q_distinct if t.lower() not in GENERIC_VENUE_TERMS and len(t) > 2]

    if p_meaningful and all(t in q_set for t in p_meaningful):
        matched_ratio = len(p_meaningful) / max(len(p_tokens), 1)
        return 0.90 + (0.09 * matched_ratio)

    if q_meaningful and all(t in p_set for t in q_meaningful):
        matched_ratio = len(q_meaningful) / max(len(p_meaningful), 1)
        return 0.85 + (0.10 * matched_ratio)"""

    if old_sim in pipe_code:
        pipe_code = pipe_code.replace(old_sim, new_sim)
        pipe_path.write_text(pipe_code, encoding="utf-8")
        print("[OK] Zaostrzono reguły matchera w pipeline.py (słowa generyczne zablokowane)")

# 3. TEST NA WYDARZENIU BARTOSZA MŁYNARSKIEGO
from src.infrastructure.scrapers.national.kupbilecik_pl import KupBilecikPlScraper
scraper = KupBilecikPlScraper(city_tag="opole")
raw_mlynarski = scraper._scrape_detail_page(
    "https://www.kupbilecik.pl/imprezy/212738/Opole/Bartosz+M%C5%82ynarski/",
    "Bartosz Młynarski", "2026-10-04", "18:00", "Miejsce X"
)

print("\n=== WYNIK TESTU SCRAPERA DLA MŁYNARSKIEGO ===")
print(json.dumps(raw_mlynarski, indent=2, ensure_ascii=False))

# Aktualizacja w SQLite dla tego konkretnego wydarzenia
db_path = Path("data/events.db")
if db_path.exists() and raw_mlynarski:
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("UPDATE events SET payload = ? WHERE city_tag = 'opole' AND payload LIKE '%Młynarski%'",
                  (json.dumps(raw_mlynarski, ensure_ascii=False),))
        conn.commit()
    print("[OK] Zaktualizowano rekord w data/events.db")
