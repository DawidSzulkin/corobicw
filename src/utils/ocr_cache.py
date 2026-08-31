import hashlib
from io import BytesIO
import json
from pathlib import Path
from PIL import Image
import pytesseract
import requests


class OcrCache:
    def __init__(self, cache_file: str = "data/ocr_cache.json"):
        self.cache_path = Path(cache_file)
        self.cache = self._load_cache()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.cache_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        temp_file.replace(self.cache_path)

    def _generate_key(self, image_url: str) -> str:
        return hashlib.md5(image_url.strip().encode("utf-8")).hexdigest()

    def get_text(self, image_url: str) -> str:
        if not image_url or not image_url.startswith("http"):
            return ""

        cache_key = self._generate_key(image_url)

        # Jeśli grafika była już czytana -> zwróć natychmiast z dysku
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Jeśli grafika jest nowa -> uruchom Tesseract
        print(f"  [OCR] Nowy plakat -> uruchamiam analizę: {image_url}")
        extracted_text = ""
        try:
            resp = self.session.get(image_url, timeout=12)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("L")
                extracted_text = pytesseract.image_to_string(img, lang="pol+eng").strip()
        except Exception as e:
            print(f"  [OCR BŁĄD] {image_url}: {e}")

        # Zapisz do cache, aby nie ponawiać
        self.cache[cache_key] = extracted_text
        self._save_cache()

        return extracted_text


ocr_engine = OcrCache()
