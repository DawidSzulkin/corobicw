import re
from pathlib import Path

file_path = Path("scripts/tools/quarantine_server.py")
if not file_path.exists():
    print("[!] Brak pliku.")
    exit(1)

code = file_path.read_text(encoding="utf-8")

# 1. Podmiana generowania opcji HTML na datalist
old_options = """options_html = "<option value=''>-- Wybierz istniejące miejsce --</option>"\n            for p in sorted_places:\n                p_id = p.get('place_id') or p.get('id', '')\n                p_name = str(p.get('name', 'Brak nazwy')).replace("'", "&#39;")\n                options_html += f"<option value='{p_id}'>{p_name}</option>\"\"\""""
# (Dopasowanie elastyczne)
code = re.sub(
    r'options_html\s*=\s*\"<option value=\'\'[^>]+>[^<]+</option>\"\s*for p in sorted_places:\s*p_id = [^\n]+\n\s*p_name = [^\n]+\n\s*options_html \+= f\"<option value=\'\{p_id\}\'>\{p_name\}</option>\"',
    r'''options_html = ""
            for p in sorted_places:
                p_id = p.get('place_id') or p.get('id', '')
                p_name = str(p.get('name', 'Brak nazwy')).replace("'", "&#39;").replace('"', '&quot;')
                options_html += f'<option value="[{p_id}] {p_name}"></option>\'''',
    code
)

# 2. Podmiana elementu select na input + datalist
code = re.sub(
    r'<select name="target_id"[^>]+>\s*\{options_html\}\s*</select>',
    r'''<input list="places_{it['city_tag']}" name="target_mapping" placeholder="Zacznij wpisywać nazwę..." required style="background:#18181b; border:1px solid #3f3f46; color:#fff; padding:8px 12px; flex:1;">
                        <datalist id="places_{it['city_tag']}">
                            {options_html}
                        </datalist>''',
    code
)

# 3. Parsowanie wyciągniętego ID w metodzie POST (/map)
old_post = r'target_id\s*=\s*params\.get\("target_id", \[""\]\)\[0\]\.strip\(\)'
new_post = '''target_mapping = params.get("target_mapping", [""])[0].strip()
            match = re.search(r'^\\[(.*?)\\]', target_mapping)
            if not match:
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return
            target_id = match.group(1).strip()'''

code = re.sub(old_post, new_post, code)

file_path.write_text(code, encoding="utf-8")
print("[OK] Zaktualizowano pole wyboru na wyszukiwarkę (datalist).")
