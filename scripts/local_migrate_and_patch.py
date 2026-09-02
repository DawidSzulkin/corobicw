import re
import sqlite3
from pathlib import Path
import sys

# --- 1. FUNKCJE FORMATUJĄCE ---
META_LABELS = [
    "Autor", "Autorka", "Autorzy", "Przekład", "Tłumaczenie",
    "Reżyseria", "Scenografia", "Kostiumy", "Muzyka", "Światło",
    "Choreografia", "Asystentka reżysera", "Asystent reżysera",
    "Kierownictwo muzyczne", "Produkcja", "Kierownik produkcji",
    "Obsada", "Występują", "Wykonawcy", "Artyści", "Prowadzenie",
    "Wydarzenie poprowadzi", "Sponsorem wydarzenia jest",
    "Informacje praktyczne", "Czas trwania"
]

def clean_and_format_description(text: str) -> str:
    if not text or len(text.strip()) < 15:
        return text.strip() if text else ""

    t = text.strip()

    # Wycięcie wstrzyknięć SEO portali biletowych (np. "Tytuł - więcej informacji")
    t = re.sub(r'(?i)(?:^|[\.\!\?\n\r]|\u2013|\u2014)\s*[^.\!?\n\r]{0,120}?-\s*więcej informacji\b[^\.\!\?\n\r]*', '. ', t)
    t = re.sub(r'(?i)[^\.\!\?\n\r]{0,80}?-\s*więcej informacji\b', '', t)
    t = re.sub(r'(?i)\bwięcej informacji\b', '', t)

    t = re.sub(r'<br\s*/?>', '\n', t, flags=re.IGNORECASE)
    t = re.sub(r'[\r\t]', ' ', t)

    # Formatowanie etykiet i metadanych
    pattern_labels = r'(?<!\n)\b(' + '|'.join(re.escape(lbl) for lbl in META_LABELS) + r')\s*:'
    t = re.sub(pattern_labels, r'\n\n* **\1:**', t)

    # Punkty i wyliczenia
    t = re.sub(r'(?<!\n)\s*(\*\s+[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż])', r'\n\n\1', t)
    t = re.sub(r'(?<!\n)\s*(\-\s+[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż])', r'\n\n* \1', t)

    # Podział narracji na akapity
    split_triggers = [
        r'(Wpadnij w wir\b)', r'(Odkryj niezwykłe życie\b)', r'(Gdy ich rodzice\b)',
        r'(Jakie wiadomości czekają\b)', r'(Przygotuj się na\b)', r'(\"[^\"]+\"\s+to\s+błyskotliwa\b)',
        r'(INFORMACJE ORGANIZACYJNE\b)', r'(UWAGA!\b)', r'(Zainteresowanych testowaniem\b)',
        r'(Testujemy programy\b)', r'(Zapisz dziecko na kolonię\b)', r'(Dlaczego warto być tam z nami\b)',
        r'(Na scenie spotkają się\b)', r'(Całość poprowadzi\b)', r'(Co się wydarzy\b)',
        r'(Siedmiu mistrzów\b)', r'(Polska Noc Kabaretowa\b)', r'(Czołowi komicy\b)',
        r'(Please,\s*Stand-up\s+prezentuje\b)'
    ]
    for trigger in split_triggers:
        t = re.sub(r'(?<!\n\n)' + trigger, r'\n\n\1', t)

    t = re.sub(r'[ ]{2,}', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip(" .-\t\r\n") + "."

# --- 2. MIGRACJA BAZY SQLITE ---
print("=== 1. CZYSZCZENIE LOKALNEJ BAZY DANYCH SQLITE ===")
db_files = list(Path("data").glob("*.db")) + list(Path(".").glob("*.db"))
migrated_count = 0

for db_path in set(db_files):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        if not cursor.fetchone():
            conn.close()
            continue
            
        cursor.execute("SELECT id, description FROM events WHERE description IS NOT NULL AND length(description) > 0")
        rows = cursor.fetchall()
        for ev_id, desc in rows:
            cleaned = clean_and_format_description(desc)
            if cleaned != desc:
                cursor.execute("UPDATE events SET description = ? WHERE id = ?", (cleaned, ev_id))
                migrated_count += 1
                
        conn.commit()
        conn.close()
        print(f"[OK] Baza {db_path.name}: zaktualizowano rekordy.")
    except Exception as e:
        print(f"[INFO] Pomijanie {db_path.name}: {e}")

print(f"[OK] Łącznie zmigrowano lokalnie rekordów: {migrated_count}")

# --- 3. AKTUALIZACJA SZABLONU templates/event_page.html ---
event_tpl = Path("templates/event_page.html")
if event_tpl.exists():
    t_content = event_tpl.read_text(encoding="utf-8")
    t_content = re.sub(
        r'\{\{\s*event\.description\s*\}\}',
        '{{ formatted_description|safe or event.description }}',
        t_content
    )
    if ".desc-meta" not in t_content:
        css_addition = """
        .event-desc p { margin-bottom: 1.15rem; line-height: 1.7; color: var(--text); }
        .desc-meta, .desc-list { margin: 1.25rem 0; padding-left: 1.5rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 0.85rem 1.25rem 0.85rem 2.25rem; }
        .desc-meta { list-style: none; padding-left: 1.25rem; }
        .desc-meta li strong { color: var(--accent, #38bdf8); margin-right: 6px; }
        .desc-meta li { padding: 0.35rem 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .desc-meta li:last-child { border-bottom: none; }
        """
        t_content = t_content.replace("</style>", f"{css_addition}\n</style>")
    event_tpl.write_text(t_content, encoding="utf-8")
    print("[OK] Zaktualizowano szablon templates/event_page.html")

# --- 4. AKTUALIZACJA RENDERER.PY ---
rend_path = Path("src/infrastructure/renderer.py")
if rend_path.exists():
    rend_txt = rend_path.read_text(encoding="utf-8")
    if "def _render_desc_to_html(" not in rend_txt:
        helper_code = """
def _render_desc_to_html(text: str) -> str:
    if not text:
        return ""
    import re
    if "<p>" in text:
        return text
    paragraphs = [p.strip() for p in text.split("\\n\\n") if p.strip()]
    blocks = []
    for p in paragraphs:
        if p.startswith("* **"):
            item_html = re.sub(r'^\\*\\s*\\*\\*([^\\*]+)\\*\\*(.*)$', r'<li><strong>\\1</strong>\\2</li>', p)
            blocks.append(f'<ul class="desc-meta">{item_html}</ul>')
        elif p.startswith("* ") or p.startswith("- "):
            item_html = re.sub(r'^[\\*\\-]\\s+(.*)$', r'<li>\\1</li>', p)
            blocks.append(f'<ul class="desc-list">{item_html}</ul>')
        else:
            blocks.append(f"<p>{p}</p>")
    res = "\\n".join(blocks)
    res = re.sub(r'</ul>\\s*<ul class="desc-meta">', '', res)
    res = re.sub(r'</ul>\\s*<ul class="desc-list">', '', res)
    return res
"""
        lines = rend_txt.splitlines()
        last_imp = 0
        for i, l in enumerate(lines):
            if l.startswith("import ") or l.startswith("from "):
                last_imp = i
        lines.insert(last_imp + 1, helper_code)
        rend_txt = "\n".join(lines)

    if "formatted_description=" not in rend_txt:
        rend_txt = re.sub(
            r'event_html\s*=\s*event_template\.render\(',
            'event_html = event_template.render(\n                formatted_description=_render_desc_to_html(getattr(ev, "description", "") or (ev.get("description", "") if isinstance(ev, dict) else "")),',
            rend_txt
        )
    rend_path.write_text(rend_txt, encoding="utf-8")
    print("[OK] Zaktualizowano renderer.py")