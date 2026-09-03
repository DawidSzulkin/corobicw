import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
import sys
import webbrowser
import http.server
import socketserver
import threading
import time

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PUBLIC_DIR = BASE_DIR / "public"

def audit_html_output():
    print("\n" + "="*55)
    print(" AUDYT SPÓJNOŚCI STATYCZNEJ STRONY (public/)")
    print("="*55)

    if not PUBLIC_DIR.exists():
        print("[BŁĄD] Katalog 'public/' nie istnieje. Uruchom najpierw generator.")
        sys.exit(1)

    html_files = list(PUBLIC_DIR.rglob("*.html"))
    print(f"Znaleziono {len(html_files)} wygenerowanych stron HTML.")

    hub_file = PUBLIC_DIR / "index.html"
    if not hub_file.exists():
        print(" [!] BRAK: Główna strona HUB (public/index.html) nie została wygenerowana!")
    else:
        print(" [OK] Główna strona wyboru miast (HUB) istnieje.")

    broken_links = []
    missing_images = []
    empty_pages = []

    for html_path in html_files:
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()

            if len(content.strip()) < 100:
                empty_pages.append(str(html_path.relative_to(PUBLIC_DIR)))
                continue

            soup = BeautifulSoup(content, "html.parser")

            # 1. Sprawdzanie lokalnych obrazków i miniaturek
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if src and not src.startswith(("http://", "https://", "data:")):
                    clean_src = src.lstrip("/").replace("/", os.sep)
                    target_file = PUBLIC_DIR / clean_src
                    if not target_file.exists():
                        missing_images.append((str(html_path.relative_to(PUBLIC_DIR)), src))

            # 2. Sprawdzanie linków wewnętrznych
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if href and not href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                    clean_href = href.split("?")[0].split("#")[0].strip("/")
                    target_path = PUBLIC_DIR / clean_href.replace("/", os.sep)
                    
                    # Link może wskazywać na plik lub katalog z index.html
                    is_valid = target_path.exists() or (target_path / "index.html").exists() or target_path.with_suffix(".html").exists()
                    if not is_valid and clean_href:
                        broken_links.append((str(html_path.relative_to(PUBLIC_DIR)), href))

        except Exception as e:
            print(f" [!] Błąd parsowania {html_path.name}: {e}")

    print("\n--- PODSUMOWANIE INTEGRALNOŚCI ---")
    if empty_pages:
        print(f"[!] Puste lub uszkodzone podstrony ({len(empty_pages)}):")
        for p in empty_pages[:5]: print(f"    - {p}")
    else:
        print("[OK] Brak pustych podstron.")

    if missing_images:
        print(f"[!] Brakujące miniatury / assety na dysku ({len(missing_images)}):")
        for page, src in missing_images[:5]: print(f"    - W pliku: {page} -> brak: {src}")
    else:
        print("[OK] Wszystkie lokalne miniatury istnieją na dysku.")

    if broken_links:
        print(f"[!] Martwe linki wewnętrzne 404 ({len(broken_links)}):")
        for page, href in broken_links[:5]: print(f"    - W pliku: {page} -> martwy link: {href}")
    else:
        print("[OK] Brak martwych linków wewnętrznych.")

    print("="*55 + "\n")

def start_server():
    os.chdir(str(PUBLIC_DIR))
    PORT = 8000
    
    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    with socketserver.TCPServer(("", PORT), SilentHandler) as httpd:
        print(f"[SERWER] Uruchomiono podgląd na: http://localhost:{PORT}")
        print("[INFO] Wciśnij Ctrl + C w konsoli, aby zatrzymać serwer.\n")
        webbrowser.open(f"http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[SERWER] Zatrzymano.")

if __name__ == "__main__":
    audit_html_output()
    start_server()
