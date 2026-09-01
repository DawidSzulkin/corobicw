from src.utils.helpers import normalize_title, slugify
from difflib import SequenceMatcher
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List

DB_PATH = Path("data/events.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]

        if columns and ("source_url" not in columns or "id" not in columns):
            cursor.execute("DROP TABLE events")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_tag TEXT NOT NULL,
                source_url TEXT UNIQUE NOT NULL,
                date_start TEXT NOT NULL,
                title TEXT NOT NULL,
                payload JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def is_event_cached(source_url: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM events WHERE source_url = ?", (source_url,))
        return cursor.fetchone() is not None


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        lead = analysis.get("editorial_lead", "")
        if lead and len(lead) > 275:
            analysis["editorial_lead"] = lead[:272].rstrip() + "..."
    return payload


def save_events_batch(city_tag: str, events: List[Dict[str, Any]]):
    if not events:
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Pobieramy wszystko dla danego miasta do RAM - wyłapie zmiany dat
        cursor.execute("SELECT id, source_url, date_start, title, payload FROM events WHERE city_tag = ?", (city_tag,))
        
        existing_by_url = {}
        existing_by_date = {}
        
        for row in cursor.fetchall():
            ex_id, ex_url, ex_date, ex_title, ex_payload = row
            if ex_url:
                existing_by_url[ex_url] = (ex_id, ex_date, ex_title, ex_payload)
            if ex_date not in existing_by_date:
                existing_by_date[ex_date] = []
            existing_by_date[ex_date].append([ex_id, ex_title, ex_payload])

        for event_data in events:
            event_data = sanitize_payload(event_data)
            
            # Zapobieganie UNIQUE constraint dla pustych URL z wadliwych scraperów
            url = event_data.get("source_url", "").strip()
            if not url:
                url = f"local://{city_tag}/{slugify(event_data.get('title', ''))}-{event_data.get('date_start', '')}"
                event_data["source_url"] = url

            date_start = event_data.get("date_start", "")
            title = event_data.get("title", "")
            norm_new = normalize_title(title)

            # 1. Update po unikalnym URL (nadpisze np. przesuniętą datę)
            if url in existing_by_url:
                ex_id = existing_by_url[url][0]
                cursor.execute(
                    "UPDATE events SET payload = ?, date_start = ?, title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(event_data, ensure_ascii=False), date_start, title, ex_id)
                )
                continue

            # 2. Szukanie logicznych duplikatów
            merged = False
            if date_start in existing_by_date:
                for ex_item in existing_by_date[date_start]:
                    ex_id, ex_title, ex_payload_json = ex_item
                    norm_ex = normalize_title(ex_title)
                    similarity = SequenceMatcher(None, norm_new, norm_ex).ratio()

                    if norm_new == norm_ex or norm_new in norm_ex or norm_ex in norm_new or similarity >= 0.65:
                        ex_payload = json.loads(ex_payload_json)

                        # Scalanie danych
                        desc_new = event_data.get("description", "")
                        desc_ex = ex_payload.get("description", "")
                        if desc_new and (not desc_ex or len(desc_new) > len(desc_ex)):
                            ex_payload["description"] = desc_new

                        price_new = event_data.get("price_range", "")
                        price_ex = ex_payload.get("price_range", "")
                        if price_new and "sprawdź" not in price_new.lower():
                            ex_payload["price_range"] = price_new
                        elif not price_ex and price_new:
                            ex_payload["price_range"] = price_new

                        img_new = event_data.get("image_url", "")
                        img_ex = ex_payload.get("image_url", "")
                        if img_new and ("unsplash" in img_ex or not img_ex):
                            ex_payload["image_url"] = img_new

                        if "analysis" in event_data and isinstance(event_data["analysis"], dict):
                            if "analysis" not in ex_payload or not isinstance(ex_payload["analysis"], dict):
                                ex_payload["analysis"] = event_data["analysis"]
                            else:
                                new_lead = event_data["analysis"].get("editorial_lead", "")
                                ex_lead = ex_payload["analysis"].get("editorial_lead", "")
                                chosen_lead = new_lead if len(new_lead) > len(ex_lead) else ex_lead
                                ex_payload["analysis"]["editorial_lead"] = chosen_lead[:272] + "..." if len(chosen_lead) > 275 else chosen_lead

                        new_payload_json = json.dumps(sanitize_payload(ex_payload), ensure_ascii=False)
                        cursor.execute(
                            "UPDATE events SET payload = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (new_payload_json, ex_id)
                        )
                        ex_item[2] = new_payload_json
                        merged = True
                        break

            if merged:
                continue

            # 3. Dodawanie nowego, niezduplikowanego rekordu
            try:
                cursor.execute("""
                    INSERT INTO events (city_tag, source_url, date_start, title, payload)
                    VALUES (?, ?, ?, ?, ?)
                """, (city_tag, url, date_start, title, json.dumps(event_data, ensure_ascii=False)))
                
                new_id = cursor.lastrowid
                new_payload_json = json.dumps(event_data, ensure_ascii=False)
                existing_by_url[url] = (new_id, date_start, title, new_payload_json)
                if date_start not in existing_by_date:
                    existing_by_date[date_start] = []
                existing_by_date[date_start].append([new_id, title, new_payload_json])
            except sqlite3.IntegrityError as e:
                # Ostateczny bezpiecznik, żeby baza się nie zawiesiła
                print(f"[DB WARN] Błąd zapisu {url}: {e}")

        conn.commit()


def save_event(city_tag: str, event_data: Dict[str, Any]) -> str:
    save_events_batch(city_tag, [event_data])
    return "processed"

def get_active_events(city_tag: str, min_date: str) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payload FROM events
            WHERE city_tag = ? AND COALESCE(json_extract(payload, '$.date_end'), date_start) >= ?
            ORDER BY date_start ASC
        """, (city_tag, min_date))
        rows = cursor.fetchall()

        clean_records = []
        for r in rows:
            data = json.loads(r[0])
            clean_records.append(sanitize_payload(data))
        return clean_records
