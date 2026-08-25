from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    @abstractmethod
    def fetch_events(self) -> List[Dict[str, Any]]:
        """
        Główna metoda pobierająca wydarzenia.
        Musi zwracać listę słowników o kluczach:
        - 'title' (str)
        - 'date' (str: YYYY-MM-DD)
        - 'url' (str)
        - 'description' (str)
        - 'source' (str)
        """
        pass