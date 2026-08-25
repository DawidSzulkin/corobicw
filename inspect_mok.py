import urllib3
import requests
from bs4 import BeautifulSoup

# Wyłączenie ostrzeżeń o braku certyfikatu SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

candidate_sources = [
    ("MOK Chemik / Kultura", "http://mok.k-k.pl"),
    ("MOK Alternatywny", "https://mokkk.pl"),
    ("MOSiR Kędzierzyn-Koźle", "https://mosirkk.pl"),
    ("Miejska Biblioteka Publiczna", "https://mbpmkk.pl"),
    ("Muzeum Ziemi Kozielskiej", "https://muzeumkozle.pl"),
    ("Kino Chemik", "https://kinochemik.pl"),
    ("Portal KK24", "https://kk24.pl"),
    ("Portal Lokalna24", "https://lokalna24.pl"),
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("=== SPRAWDZANIE LISTY ŹRÓDEŁ ===")

for name, url in candidate_sources:
    try:
        resp = requests.get(url, headers=headers, timeout=6, verify=False, allow_redirects=True)
        final_url = resp.url
        
        # Odrzucenie obcych domen (np. renska wieś)
        if "renskawies" in final_url:
            print(f"[BŁĘDNY REDIRECT] {name} ({url}) -> Przekierowano do obcej domeny: {final_url}")
            continue

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else "Brak tytułu"
            print(f"\n[DZIAŁA 200] {name}")
            print(f"  Adres:  {final_url}")
            print(f"  Tytuł:  {title}")
            
            # Wypisz 3 przykładowe linki z menu
            sample_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                txt = a.get_text(strip=True)
                if href and txt and len(txt) > 3 and not href.startswith(("#", "javascript:", "mailto:")):
                    sample_links.append(f"{txt[:25]} -> {href[:40]}")
                if len(sample_links) >= 3:
                    break
            if sample_links:
                print(f"  Linki:  {', '.join(sample_links)}")
        else:
            print(f"[{resp.status_code}] {name} ({url})")
            
    except Exception as e:
        print(f"[NIEDOSTĘPNY] {name} ({url}) -> Błąd połączenia")