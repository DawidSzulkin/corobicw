import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Optional
from PIL import Image
import requests

from src.db import DB_PATH

try:
    from rapidocr_onnxruntime import RapidOCR
    _ocr_engine = RapidOCR()
except ImportError:
    _ocr_engine = None

CACHE_FILE = Path("data/ocr_cache.json")
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


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


def clean_ocr_with_ollama(raw_text: str, model_name: str = "qwen2.5:3b") -> str:
    """Czyści surowy tekst OCR za pomocą Ollama (JSON format)."""
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
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "system": system_instruction,
                "prompt": f"TEKST Z PLAKATU:\n{raw_text}",
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.2}
            },
            timeout=15
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
            clean_path = image_path_or_url.lstrip("/")
            local_file = DOCS_DIR / clean_path
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


def process_image_with_cache(image_identifier: str, cache: dict) -> str:
    img_hash = _get_hash(image_identifier)
    if img_hash in cache:
        return cache[img_hash]

    raw_ocr = extract_text_from_image(image_identifier)
    cleaned_desc = ""
    if len(raw_ocr.strip()) > 30:
        cleaned_desc = clean_ocr_with_ollama(raw_ocr)

    cache[img_hash] = cleaned_desc
    _save_cache(cache)
    return cleaned_desc


def enrich_missing_descriptions(city_tag: str):
    cache = _load_cache()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, payload FROM events WHERE city_tag = ?", (city_tag,))
        rows = cursor.fetchall()

        enriched_count = 0
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
                    cleaned_desc = process_image_with_cache(img_url, cache)
                    if cleaned_desc:
                        event["description"] = cleaned_desc
                        if "analysis" in event and isinstance(event["analysis"], dict):
                            event["analysis"]["editorial_lead"] = cleaned_desc[:272] + "..." if len(cleaned_desc) > 275 else cleaned_desc
                            event["analysis"]["full_description"] = cleaned_desc

                        cursor.execute(
                            "UPDATE events SET payload = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (json.dumps(event, ensure_ascii=False), event_id)
                        )
                        conn.commit()
                        enriched_count += 1
            except Exception as err:
                print(f"  [Błąd wzbogacania rekordu {event_id}]: {err}")
                continue

    print(f"[ENRICHER] Zaktualizowano opisy w bazie: {enriched_count} rekordów.")
