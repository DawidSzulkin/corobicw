import os
from pathlib import Path

BASE_DIR = Path.cwd()
search_terms = [
    "src/public", 
    "src\\\\public", 
    "../../public", 
    "../public", 
    "..\\..\\public", 
    "..\\public"
]

print("=== SZUKANIE ODWOŁAŃ DO src/public W KODZIE ===")
found_issues = False

for root, dirs, files in os.walk(BASE_DIR):
    # Pomijamy foldery ignorowane i wynikowe
    if any(part.startswith('.') or part in ['__pycache__', 'node_modules', 'public', 'data', 'docs'] for part in Path(root).parts):
        continue
        
    for file in files:
        if not file.endswith(('.py', '.html', '.js', '.css', '.json', '.yaml', '.yml')):
            continue
            
        file_path = Path(root) / file
        try:
            content = file_path.read_text(encoding='utf-8')
            for i, line in enumerate(content.splitlines()):
                for term in search_terms:
                    # Szukamy wystąpień, ignorując te, które mogą być po prostu w HTML jako linki (choć HTML w src to zazwyczaj szablony)
                    if term in line:
                        print(f"Plik: {file_path.relative_to(BASE_DIR)} (Linia {i+1})")
                        print(f" -> {line.strip()}")
                        found_issues = True
                        break # Wystarczy raz w danej linii
        except Exception:
            pass

if not found_issues:
    print("\n[CZYSTO] Nie znaleziono żadnych podejrzanych odwołań do 'src/public' w kodzie.")
