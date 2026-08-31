from abc import ABC, abstractmethod
from datetime import timedelta
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
import requests_cache
import urllib3

from src.utils.helpers import slugify

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Główny katalog projektu (portal/)
ROOT_DIR = Path(__file__).resolve().parents[3]

class BaseScraper(ABC):
    def __init__(self, source_name: str, base_url: str, cache_expire_hours: int = 12):
        self.source_name = source_name
        self.base_url = base_url
        
        # Centralny katalog miniatur WebP w głównym public/
        self.thumb_dir = os.path.abspath(ROOT_DIR / "public" / "assets" / "thumbnails")
        os.makedirs(self.thumb_dir, exist_ok=True)
        
        # Centralny kesz HTTP w głównym data/
        cache_dir = os.path.abspath(ROOT_DIR / "data")
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
        full_url = urljoin(self.base_url, url)
        response = self.session.get(full_url, params=params, verify=False, timeout=(3.05, 10))
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")

    def save_thumbnail(self, img_url: str, title: str, prefix: str = "") -> str:
        if not img_url:
            return ""

        full_img_url = urljoin(self.base_url, img_url)
        clean_title = slugify(title)
        filename = f"{prefix}_{clean_title}.webp" if prefix else f"{clean_title}.webp"
        target_path = os.path.join(self.thumb_dir, filename)
        rel_path = f"/assets/thumbnails/{filename}"

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            return rel_path

        try:
            resp = self.session.get(full_img_url, timeout=(3.05, 10), verify=False)
            if resp.status_code == 200 and resp.content:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                max_width = 600
                if img.width > max_width:
                    height = int((max_width / img.width) * img.height)
                    img = img.resize((max_width, height), Image.Resampling.LANCZOS)
                
                img.save(target_path, "WEBP", quality=80)
                return rel_path
        except Exception:
            pass

        return ""

    @abstractmethod
    def fetch_events(self) -> List[Dict[str, Any]]:
        pass
