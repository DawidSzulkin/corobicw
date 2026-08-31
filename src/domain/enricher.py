import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Optional, List, Tuple
from PIL import Image
import requests
import yaml
import concurrent.futures

from src.infrastructure.db import DB_PATH

try:
    from rapidocr_onnxruntime import RapidOCR
    _ocr_engine = RapidOCR()
except ImportError:
    _ocr_engine = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_FILE = BASE_DIR / "data" / "ocr_cache.json"
THUMBNAILS_DIR = BASE_DIR / "public" / "assets" / "thumbnails"
GLOBAL_CFG_PATH = BASE_DIR / "config" / "global.yaml"


def _load_global_config() -> dict:
    if GLOBAL_CFG_PATH.exists():
        try:
            with open(GLOBAL_CFG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CACHE_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    temp_file.replace(CACHE_FILE)


def _get_hash(val: str) -> str:
    return hashlib.md5(val.strip().encode("utf-8")).hexdigest()


def clean_ocr_with_ollama(raw_text: str, ollama_cfg: dict) -> str:
    url = ollama_cfg.get("url", "http://localhost:11434/api/generate")
    model_name = ollama_cfg.get("model", "qwen2.5:3b")
    timeout = ollama_cfg.get("timeout", 20)
    temp = ollama_cfg.get("temperature", 0.2)

    system_instruction = (
        "Jesteś modułem czyszczącym OCR dla portalu miejskiego. "
        "Na podstawie odczytanego tekstu z plakatu przygotuj krótki, rzeczowy opis wydarzenia po polsku (1-3 zdania). "
        "Zasady bezwzględne:\n"
        "1. Nie pisz zwrotów typu: 'Oto opis', 'Poprawiona wersja', 'Zadanie wykonane'.\n"
        "2. Nie zmyślaj faktów ani liczb, których nie ma w tekście.\n"
        "3. Zwróć WYŁĄCZNIE obiekt JSON o strukturze: {\"description\": \"treść opisu\"}"
    )

    try:
        resp = requests.post(
            url,
            json={
                "model": model_name,
                "system": system_instruction,
                "prompt": f"TEKST Z PLAKATU:\n{raw_text}",
                "format": "json",
                "stream": False,
                "options": {"temperature": temp}
            },
            timeout=timeout
        )

        if resp.status_code == 200:
            data = json.loads(resp.json().get("response", "{}"))
            clean_text = data.get("description", "").strip()
            clean_text = re.sub(
                r"^(oto|poniżej|zadanie|poprawion[ay]|zredagowan[ay]|tekst|informacj[ae]|zgodnie|na podstawie).*?:\s*",
                "",
                clean_text,
                flags=re.IGNORECASE
            ).strip()

            if clean_text:
                return clean_text
    except Exception:
        pass

    fallback = re.sub(r"\s+", " ", raw_text).strip()
    return fallback[:250]


def extract_text_from_image(image_path_or_url: str) -> str:
    if not _ocr_engine or not image_path_or_url:
        return ""

    try:
        img: Optional[Image.Image] = None

        if image_path_or_url.startswith(("http://", "https://")):
            resp = requests.get(image_path_or_url, timeout=(3.0, 8.0))
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        else:
            filename = Path(image_path_or_url).name
            local_file = THUMBNAILS_DIR / filename
            if local_file.exists():
                img = Image.open(local_file).convert("RGB")

        if img is None:
            return ""

        img.thumbnail((1200, 1200))
        result, _ = _ocr_engine(img)
        if result:
            lines = [line[1] for line in result if line[2] > 0.5]
            return " ".join(lines)
    except Exception as e:
        print(f"    [OCR Błąd dla {image_path_or_url[:40]}]: {e}")

    return ""


def enrich_missing_descriptions(city_tag: str):
    cache = _load_cache()
    global_cfg = _load_global_config()
    ollama_cfg = global_cfg.get("ollama", {})

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, payload FROM events WHERE city_tag = ?", (city_tag,))
        rows = cursor.fetchall()

    tasks_to_enrich = []
    for event_id, title, payload_json in rows:
        try:
            event = json.loads(payload_json)
            desc = event.get("description", "").strip()
            img_url = event.get("image_url", "").strip()

            is_valid_image = bool(img_url and "unsplash" not in img_url.lower())
            is_boilerplate = (
                not desc
                or len(desc) < 60
                or desc.lower().startswith((
                    "wydarzenie:", "wydarzenie biletowane:", "wydarzenie miejskie:",
                    "wydarzenie sportowe:", "spektakl w", "koncert w"
                ))
            )

            if is_boilerplate and is_valid_image:
                tasks_to_enrich.append((event_id, event, img_url))
        except Exception:
            continue

    if not tasks_to_enrich:
        print(f"[ENRICHER] Brak brakujących opisów dla '{city_tag}'.")
        return

    def process_item(item: Tuple[int, dict, str]) -> Optional[Tuple[int, dict]]:
        ev_id, ev_data, img_identifier = item
        img_hash = _get_hash(img_identifier)
        
        cleaned_desc = cache.get(img_hash)
        if not cleaned_desc:
            raw_ocr = extract_text_from_image(img_identifier)
            if len(raw_ocr.strip()) > 30:
                cleaned_desc = clean_ocr_with_ollama(raw_ocr, ollama_cfg)
            else:
                cleaned_desc = ""
            cache[img_hash] = cleaned_desc

        if cleaned_desc:
            ev_data["description"] = cleaned_desc
            if "analysis" in ev_data and isinstance(ev_data["analysis"], dict):
                ev_data["analysis"]["editorial_lead"] = cleaned_desc[:272] + "..." if len(cleaned_desc) > 275 else cleaned_desc
                ev_data["analysis"]["full_description"] = cleaned_desc
            return ev_id, ev_data
        return None

    enriched_records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(process_item, tasks_to_enrich)
        for res in results:
            if res:
                enriched_records.append(res)

    _save_cache(cache)

    if enriched_records:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            for ev_id, ev_data in enriched_records:
                cursor.execute(
                    "UPDATE events SET payload = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(ev_data, ensure_ascii=False), ev_id)
                )
            conn.commit()

    print(f"[ENRICHER] Zaktualizowano opisy w bazie: {len(enriched_records)} rekordów.")