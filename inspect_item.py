import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

api_url = "https://www.mok.kedzierzyn-kozle.com.pl/index.php?option=com_minitekwall&task=masonry.getContent&widget_id=1&page=1"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.mok.kedzierzyn-kozle.com.pl/wydarzenia"
}

resp = requests.get(api_url, headers=headers, verify=False)
soup = BeautifulSoup(resp.text, "html.parser")
first_item = soup.select_one(".mnwall-item")

if first_item:
    print("=== ATRYBUTY KAFELKA ===")
    print(first_item.attrs)
    print("\n=== ZNALEZIONE LINKI WEWNĄTRZ ===")
    for a in first_item.find_all("a"):
        print(f"Tag <a>: href='{a.get('href')}' | class='{a.get('class')}' | text='{a.get_text(strip=True)}' | attrs={a.attrs}")
    print("\n=== KOD HTML PIERWSZEGO KAFELKA ===")
    print(first_item.prettify()[:1000])
else:
    print("Nie znaleziono .mnwall-item")