from pathlib import Path
import re

renderer_path = Path("src/renderer.py")
code = renderer_path.read_text(encoding="utf-8")

print("=" * 80)
print("=== 1. ZMIENNE CSS I SEKCJE HEAD W src/renderer.py ===")
print("=" * 80)
for match in re.finditer(r'([A-Z0-9_]*CSS[A-Z0-9_]*\s*=\s*(?:"""|\'\'\')[\s\S]*?(?:"""|\'\'\'))', code):
    print(match.group(1)[:250] + "\n... [skrócono] ...\n")

print("=" * 80)
print("=== 2. METODY RENDERUJĄCE WIZYTÓWKI I KARTY WYDARZEŃ ===")
print("=" * 80)
lines = code.splitlines()
for i, line in enumerate(lines):
    if any(k in line for k in ["def render", "def _render", "class "]):
        print(f"Linia {i+1:>4}: {line}")

print("\n" + "=" * 80)
print("=== 3. FRAGMENT KODU GENERUJĄCY KARTĘ WYDARZENIA ===")
print("=" * 80)
# Szukamy metody karty wydarzenia
card_match = re.search(r'def\s+.*?(?:event|card)[\s\S]*?(?=\n    def|\nclass|\Z)', code)
if card_match:
    print(card_match.group(0)[:800])
else:
    print("Nie znaleziono pojedynczej metody karty – sprawdzam wystąpienia 'venue':")
    for i, line in enumerate(lines):
        if "venue" in line or "location" in line:
            print(f"Linia {i+1:>4}: {line.strip()}")
