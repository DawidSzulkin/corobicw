import re
from pathlib import Path

renderer_path = Path("src/infrastructure/renderer.py")
if renderer_path.exists():
    content = renderer_path.read_text(encoding="utf-8")
    
    # Upewniamy się, że biblioteka shutil jest zaimportowana
    if "import shutil" not in content:
        content = "import shutil\n" + content
    
    # Szukamy miejsca, gdzie tworzony jest folder wydarzeń i dodajemy czyszczenie
    target = r'events_dir = city_dir / "wydarzenia"\s*events_dir\.mkdir\(parents=True, exist_ok=True\)'
    patch = """events_dir = city_dir / "wydarzenia"
        if events_dir.exists():
            shutil.rmtree(events_dir)
        events_dir.mkdir(parents=True, exist_ok=True)"""
        
    if "shutil.rmtree(events_dir)" not in content:
        content = re.sub(target, patch, content)
        renderer_path.write_text(content, encoding="utf-8")
        print("[OK] Dodano mechanizm twardego resetu folderu /wydarzenia/ przed każdym renderowaniem.")
    else:
        print("[INFO] Mechanizm czyszczenia wydarzeń jest już wdrożony.")
