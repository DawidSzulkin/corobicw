from pathlib import Path

print("=" * 80)
print("=== POKAŻ KOD KARTY WYDARZENIA W SZABLONIE ===")
print("=" * 80)

for tf in Path("templates").rglob("*.html"):
    code = tf.read_text(encoding="utf-8")
    if "event-card" in code and "meta-bottom" in code:
        print(f"\n--- PLIK: {tf.name} ---")
        lines = code.splitlines()
        
        # Wypisz wszystkie pętle for w pliku
        print("ZNALEZIONE PĘTLE JINJA:")
        for line in lines:
            if "{% for " in line:
                print("  " + line.strip())
                
        print("\nSTRUKTURA KARTY:")
        for i, line in enumerate(lines):
            if "event-card" in line:
                start = max(0, i - 3)
                end = min(len(lines), i + 25)
                for j in range(start, end):
                    print(f"L{j+1:<3}: {lines[j]}")
                break
