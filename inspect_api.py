import json
import re
from bs4 import BeautifulSoup
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://teatr.bielsko.pl/repertuar"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

resp = requests.get(url, headers=headers, verify=False, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

# 1. Sprawdzenie osadzonego stanu __NEXT_DATA__ lub __NUXT__
next_data = soup.find("script", id="__NEXT_DATA__")
if next_data and next_data.string:
    print("[WYKRYTO] Dane w obiekcie __NEXT_DATA__!")
    try:
        data = json.loads(next_data.string)
        with open("next_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Zapisano dane do pliku: next_data.json")
    except Exception as e:
        print("Blad parsowania JSON __NEXT_DATA__:", e)

# 2. Sprawdzenie endpointów API w plikach JS
scripts = [s.get("src", "") for s in soup.find_all("script") if s.get("src")]
print(f"\nZalezne pliki skryptow JS ({len(scripts)}):")
for s in scripts:
    print(" ", s)

# 3. Poszukiwanie wzorcow API/GraphQL w tresci strony
api_matches = re.findall(r"['\"](/api/[^'\"]+|https?://[^'\"]+/api/[^'\"]+|https?://[^'\"]+graphql[^'\"]*)['\"]", resp.text)
if api_matches:
    print(f"\nPotencjalne endpointy API znalezione w HTML ({len(api_matches)}):")
    for api in set(api_matches):
        print(" ", api)