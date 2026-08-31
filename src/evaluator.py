import json
import requests
import re
from typing import Dict, Any, Optional
from pydantic import ValidationError
from src.core.models import EventAnalysis, FullEventPage

class EventEvaluator:
    def __init__(self, global_cfg: Dict[str, Any], city_cfg: Dict[str, Any]):
        self.ollama_cfg = global_cfg["ollama"]
        self.prompts = city_cfg["prompts"]

    def _slugify(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        return re.sub(r'[-\s]+', '-', text).strip('-')

    def evaluate(self, event: Dict[str, Any]) -> Optional[FullEventPage]:
        clean_desc = (event.get("description") or "").strip()[:800]
        if not clean_desc:
            clean_desc = f"Wydarzenie miejskie: {event.get('title')}."

        user_content = self.prompts["user_template"].format(
            title=event.get("title", ""),
            date=event.get("date", ""),
            description=clean_desc
        )

        payload = {
            "model": self.ollama_cfg["model"],
            "prompt": f"{self.prompts['system']}\n\n{user_content}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 350
            }
        }

        try:
            resp = requests.post(self.ollama_cfg["url"], json=payload, timeout=self.ollama_cfg["timeout"])
            resp.raise_for_status()
            parsed = json.loads(resp.json().get("response", "{}"))
            
            analysis = EventAnalysis(**parsed)
            slug = self._slugify(f"{event.get('date', 'event')}-{event.get('title', 'details')[:30]}")

            return FullEventPage(
                slug=slug,
                title=event["title"],
                date_formatted=event["date"],
                raw_date=event["date"],
                image_url=event.get("image_url", ""),
                source_url=event["url"],
                analysis=analysis
            )
        except Exception as e:
            print(f"    [!] Błąd ewaluacji dla '{event.get('title')}': {e}")
            return None
