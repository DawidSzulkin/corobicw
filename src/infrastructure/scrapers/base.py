from abc import ABC, abstractmethod
from datetime import timedelta
import io
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
import requests_cache
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BaseScraper(ABC):
    def __init__(self, source_name: str, base_url: str, cache_expire_hours: int = 12):
        self.source_name = source_name
        self.base_url = base_url
        
        # Centralna miniatura WebP w katalogu public
        self.thumb_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../public/assets/thumbnails"))
        os.makedirs(self.thumb_dir, exist_ok=True)
        
        # Centralna baza cache dla zapytań HTTP
        cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "http_cache")

        self.session = requests_cache.CachedSession(
            cache_path,
            backend="sqlite",
            expire_after=timedelta(hours=cache_expire_hours),
            allowable_methods=["GET", "POST"],
            stale_if_error=True
        )
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pl,en-US;q=0.7,en;q=0.3"
        })

    def get_soup(self, url: str, params: Optional[dict] = None) -> BeautifulSoup:
        """Pobiera stronę i zwraca BeautifulSoup na bazie surowych bajtów UTF-8."""
        full_url = urljoin(self.base_url, url)
        resp = self.session.get(full_url, params=params, timeout=20, verify=False)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    def save_thumbnail(self, remote_img_url: str, title: str, prefix: str = "") -> str:
        """Pobiera i kompresuje plakat do WebP tylko jeśli nie ma go jeszcze na dysku."""
        if not remote_img_url:
            return ""

        tag = f"{prefix}_{self.source_name}" if prefix else self.source_name
        safe_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", title.lower()).strip("_")
        filename = f"{tag}_{safe_slug}.webp"
        disk_path = os.path.join(self.thumb_dir, filename)
        web_path = f"/assets/thumbnails/{filename}"

        if os.path.exists(disk_path):
            return web_path

        try:
            full_img_url = urljoin(self.base_url, remote_img_url)
            resp = self.session.get(full_img_url, timeout=(3.0, 8.0), verify=False)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                max_w = 400
                if img.width > max_w:
                    ratio = max_w / float(img.width)
                    new_h = int(float(img.height) * float(ratio))
                    img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)
                
                img.save(disk_path, "WEBP", quality=75, optimize=True)
                return web_path
        except Exception as e:
            print(f"[{self.source_name}] Błąd generowania miniatury dla '{title[:30]}': {e}")

        return ""

    @abstractmethod
    def fetch_events(self) -> List[Dict[str, Any]]:
        """Główna metoda pobierająca wydarzenia."""
        pass
