from pathlib import Path
p = Path("src/infrastructure/scrapers/national/kupbilecik_pl.py")
if p.exists():
    c = p.read_text(encoding="utf-8")
    old = "if not any(slug in norm_url for slug in self.required_slugs): continue"
    new = old + "\n                if 'opole' in self.city_tag and 'lubelskie' in norm_url: continue"
    if "lubelskie" not in c and old in c:
        p.write_text(c.replace(old, new), encoding="utf-8")
        print("[OK] Zablokowano fałszywe Opole Lubelskie.")
