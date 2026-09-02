import re
import sys
from pathlib import Path

# 1. TWARDY RESET PLIKÓW DO STANU Z REPOZYTORIUM
import subprocess
subprocess.run(["git", "checkout", "src/infrastructure/renderer.py"], capture_output=True)
subprocess.run(["git", "checkout", "templates/event_page.html"], capture_output=True)

# 2. WSTRZYKNIĘCIE NIEZAWODNEGO MECHANIZMU DO RENDERER.PY
rend_path = Path("src/infrastructure/renderer.py")
r_code = rend_path.read_text(encoding="utf-8")

choke_point_processor = """
def _brutal_format_desc(text: str) -> str:
    if not text: return ""
    import re
    
    # 1. Usuwanie spamu SEO bez ograniczeń regexa
    while True:
        idx = text.lower().find("- więcej informacji")
        if idx == -1: break
        
        # Cofa się do 150 znaków, szukając kropki, wykrzyknika, pytajnika lub nowej linii
        cut_start = max(0, idx - 150)
        for i in range(idx, max(-1, idx - 150), -1):
            if text[i] in ['.', '!', '?', '\\n']:
                cut_start = i + 1
                break
                
        text = text[:cut_start] + " " + text[idx + 19:]
        
    text = re.sub(r'<br\\s*/?>', '\\n', text, flags=re.IGNORECASE)
    
    # 2. Wymuszenie twardych podziałów dla dopisków
    text = text.replace(" P.S.", "\\n\\nP.S.")
    text = text.replace(" UWAGA", "\\n\\nUWAGA")
    
    # 3. Dynamiczny chunking zdań na akapity
    if "\\n\\n" not in text:
        sentences = re.split(r'(?<=[.!?…])\\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ"„\\U00010000-\\U0010ffff])', text)
        paragraphs = []
        curr = []
        clen = 0
        for s in sentences:
            if s.startswith("P.S.") or s.startswith("UWAGA"):
                if curr: paragraphs.append(" ".join(curr))
                curr = []
                clen = 0
            curr.append(s)
            clen += len(s)
            if clen > 200:
                paragraphs.append(" ".join(curr))
                curr = []
                clen = 0
        if curr:
            paragraphs.append(" ".join(curr))
        text = "\\n\\n".join(paragraphs)

    # 4. Konwersja do HTML
    paragraphs = [p.strip() for p in text.split("\\n\\n") if p.strip()]
    out = []
    for p in paragraphs:
        if p.startswith("P.S."):
            out.append(f'<p class="desc-ps"><em>{p}</em></p>')
        else:
            out.append(f'<p>{p}</p>')
            
    return "\\n".join(out)
"""

if "_brutal_format_desc" not in r_code:
    lines = r_code.splitlines()
    last_imp = 0
    for i, l in enumerate(lines):
        if l.startswith("import ") or l.startswith("from "):
            last_imp = i
    lines.insert(last_imp + 1, choke_point_processor)
    r_code = "\n".join(lines)

# Wstrzyknięcie procesora tuż przed wywołaniem event_template.render()
r_code = re.sub(
    r'(event_html\s*=\s*event_template\.render\()',
    r'\1\n                formatted_desc=_brutal_format_desc(getattr(ev, "description", "") or (ev.get("description", "") if isinstance(ev, dict) else "")),',
    r_code
)
rend_path.write_text(r_code, encoding="utf-8")
print("[OK] Zaktualizowano renderer.py: wdrożono twardy punkt kontrolny opisu.")

# 3. AKTUALIZACJA SZABLONU
event_tpl = Path("templates/event_page.html")
t_code = event_tpl.read_text(encoding="utf-8")

# Podmiana zmiennej na wygenerowany HTML
t_code = re.sub(
    r'\{\{\s*event\.description[^}]*\}\}',
    '{{ formatted_desc | safe }}',
    t_code
)

if ".desc-ps" not in t_code:
    css_block = """
    .event-desc p { margin-bottom: 1.25rem; line-height: 1.75; font-size: 1rem; color: #e2e8f0; }
    .event-desc .desc-ps { color: var(--text-muted, #94a3b8); margin-top: 1.5rem; font-style: italic; }
    """
    t_code = t_code.replace("</style>", f"{css_block}\n</style>")

event_tpl.write_text(t_code, encoding="utf-8")
print("[OK] Zaktualizowano templates/event_page.html")