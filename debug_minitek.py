import urllib3
import requests
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://www.mok.kedzierzyn-kozle.com.pl"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{base_url}/wydarzenia"
}

# Test 1: GET z różnymi kombinacjami parametrów
urls_to_test = [
    f"{base_url}/index.php?option=com_minitekwall&task=masonry.getContent&widget_id=1&page=1",
    f"{base_url}/index.php?option=com_minitekwall&task=masonry.getContent&widget_id=1&page=1&grid=masonry",
    f"{base_url}/index.php?option=com_minitekwall&task=masonry.getContent&widget_id=1&page=0",
    f"{base_url}/index.php?option=com_minitekwall&task=masonry.getFilters&widget_id=1"
]

print("=== 1. TESTY METODY GET ===")
for url in urls_to_test:
    try:
        r = requests.get(url, headers=headers, timeout=8, verify=False)
        print(f"\nURL: {url}")
        print(f"Status: {r.status_code} | Content-Type: {r.headers.get('Content-Type')}")
        print(f"Długość odpowiedzi: {len(r.text)} znaków")
        print(f"Początek (pierwsze 200 znaków): {r.text[:200]}")
    except Exception as e:
        print(f"Błąd GET dla {url}: {e}")

# Test 2: POST
print("\n=== 2. TESTY METODY POST ===")
post_url = f"{base_url}/index.php?option=com_minitekwall&task=masonry.getContent"
data_payloads = [
    {"widget_id": 1, "page": 1},
    {"widget_id": "1", "page": "1", "grid": "masonry"},
]

for payload in data_payloads:
    try:
        r = requests.post(post_url, data=payload, headers=headers, timeout=8, verify=False)
        print(f"\nPOST Payload: {payload}")
        print(f"Status: {r.status_code} | Content-Type: {r.headers.get('Content-Type')}")
        print(f"Długość: {len(r.text)} znaków")
        print(f"Początek: {r.text[:200]}")
    except Exception as e:
        print(f"Błąd POST: {e}")