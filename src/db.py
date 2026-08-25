from difflib import SequenceMatcher
import json
from pathlib import Path
import re
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


def normalize_title(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\b20\d{2}\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 2]
    return " ".join(tokens)


def is_event_cached(source_url: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM events WHERE source_url = ?", (source_url,))
        return cursor.fetchone() is not None


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wymusza limity znaków na polach przed Pydanticem."""
    lead = payload.get("analysis", {}).get("editorial_lead", "")
    if lead and len(lead) > 275:
        payload["analysis"]["editorial_lead"] = lead[:272].rstrip() + "..."
    return payload


def save_event(city_tag: str, event_data: Dict[str, Any]) -> str:
    event_data = sanitize_payload(event_data)
    url = event_data.get("source_url", "")
    date_start = event_data.get("date_start", "")
    title = event_data.get("title", "")
    norm_new = normalize_title(title)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, payload FROM events WHERE source_url = ?", (url,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE events SET payload = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(event_data, ensure_ascii=False), row[0])
            )
            conn.commit()
            return "updated_url"

        cursor.execute("SELECT id, title, payload FROM events WHERE city_tag = ? AND date_start = ?", (city_tag, date_start))
        existing_rows = cursor.fetchall()

        for ex_id, ex_title, ex_payload_json in existing_rows:
            norm_ex = normalize_title(ex_title)
            similarity = SequenceMatcher(None, norm_new, norm_ex).ratio()

            if norm_new in norm_ex or norm_ex in norm_new or similarity >= 0.65:
                ex_payload = json.loads(ex_payload_json)
                
                # Scalanie opisów z zachowaniem limitu długości
                new_lead = event_data.get("analysis", {}).get("editorial_lead", "")
                ex_lead = ex_payload.get("analysis", {}).get("editorial_lead", "")
                chosen_lead = new_lead if len(new_lead) > len(ex_lead) else ex_lead
                ex_payload["analysis"]["editorial_lead"] = chosen_lead[:272] + "..." if len(chosen_lead) > 275 else chosen_lead

                new_price = event_data.get("analysis", {}).get("ticket_info", {}).get("price_range", "")
                if new_price and "sprawdź bilety" not in new_price.lower():
                    ex_payload["analysis"]["ticket_info"]["price_range"] = new_price

                if "unsplash" in ex_payload.get("image_url", "") and "unsplash" not in event_data.get("image_url", ""):
                    ex_payload["image_url"] = event_data["image_url"]

                cursor.execute(
                    "UPDATE events SET payload = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(sanitize_payload(ex_payload), ensure_ascii=False), ex_id)
                )
                conn.commit()
                return "merged_duplicate"

        cursor.execute("""
            INSERT INTO events (city_tag, source_url, date_start, title, payload)
            VALUES (?, ?, ?, ?, ?)
        """, (city_tag, url, date_start, title, json.dumps(event_data, ensure_ascii=False)))
        conn.commit()
        return "created"


def get_active_events(city_tag: str, min_date: str) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payload FROM events
            WHERE city_tag = ? AND date_start >= ?
            ORDER BY date_start ASC
        """, (city_tag, min_date))
        rows = cursor.fetchall()
        
        # Zabezpieczenie danych wychodzących do Pydantic
        clean_records = []
        for r in rows:
            data = json.loads(r[0])
            clean_records.append(sanitize_payload(data))
        return clean_records