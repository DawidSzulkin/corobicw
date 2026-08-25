import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://www.mok.kedzierzyn-kozle.com.pl/wydarzenia"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

resp = requests.get(url, headers=headers, verify=False)
soup = BeautifulSoup(resp.text, "html.parser")

print("=== 1. ZNALEZIONE RAMKI IFRAME ===")
iframes = soup.find_all("iframe")
for f in iframes:
    print(f"  -> src: {f.get('src')}")
if not iframes:
    print("  Brak tagów <iframe>.")

print("\n=== 2. SKRYPTY ZEWNĘTRZNE I ENDPOINTY API ===")
for s in soup.find_all("script", src=True):
    src = s["src"]
    if any(k in src.lower() for k in ["event", "bilety", "widget", "calendar", "repertuar", "ajax"]):
        print(f"  -> {src}")

print("\n=== 3. KOD JS INLINE (POTENCJALNE KONFIGURACJE AJAX) ===")
for s in soup.find_all("script", src=False):
    code = s.get_text()
    if any(k in code.lower() for k in ["fetch(", "ajax", "widget", "events", "json"]):
        for line in code.split("\n"):
            if any(k in line.lower() for k in ["url:", "endpoint", "widget_id", "events", "api"]):
                print(f"  [JS]: {line.strip()[:120]}")