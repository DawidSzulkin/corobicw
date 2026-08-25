from datetime import datetime
import json
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://teatr.bielsko.pl"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://teatr.bielsko.pl/repertuar"
}

# Test 1: Zapytanie bez parametrów
print("--- Test 1: /api/repertoire ---")
resp1 = requests.get(f"{base_url}/api/repertoire", headers=headers, verify=False, timeout=10)
print(f"Status: {resp1.status_code} | Długość: {len(resp1.text)}")

# Test 2: Zapytanie z parametrem daty (bieżący miesiąc)
now = datetime.now()
print(f"\n--- Test 2: /api/repertoire?month={now.month}&year={now.year} ---")
resp2 = requests.get(f"{base_url}/api/repertoire?month={now.month}&year={now.year}", headers=headers, verify=False, timeout=10)
print(f"Status: {resp2.status_code} | Długość: {len(resp2.text)}")

# Zapisanie pierwszej udanej odpowiedzi JSON do pliku
target_resp = resp1 if resp1.status_code == 200 and len(resp1.text) > 100 else resp2

if target_resp.status_code == 200:
    try:
        data = target_resp.json()
        with open("teatr_api_sample.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n[SUKCES] Zapisano odpowiedź JSON do pliku: teatr_api_sample.json")
        
        # Wyświetlenie próbki danych
        if isinstance(data, list) and len(data) > 0:
            print("Przykładowy rekord:", json.dumps(data[0], ensure_ascii=False, indent=2))
        elif isinstance(data, dict):
            print("Klucze w obiekcie JSON:", list(data.keys()))
    except Exception as e:
        print("Odpowiedź nie jest poprawnym JSON-em:", e)
        print("Treść odpowiedzi:", target_resp.text[:300])
else:
    print("\nEndpoint wymaga innych parametrów. Podgląd rsc_payload.txt:")
    with open("rsc_payload.txt", "r", encoding="utf-8") as f:
        print(f.read()[:500])