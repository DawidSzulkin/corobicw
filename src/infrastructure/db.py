def _get_url_priority(url: str) -> tuple[int, str]:
    u = (url or "").lower()
    if "kupbilecik" in u: return (100, "KupBilecik")
    if "biletyna" in u: return (95, "Biletyna")
    if "ebilet" in u: return (90, "eBilet")
    if "eventim" in u: return (85, "Eventim")
    if "goingapp" in u: return (80, "Going.")
    if "ticketmaster" in u: return (75, "Ticketmaster")
    if any(k in u for k in ["teatr", "bck", "cavatina", "galeriabielska", "banialuka", "mok", "mosir", "mbp"]):
        return (50, "Organizator")
    return (10, "Strona źródłowa")


from datetime import datetime
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
            url = event_data.get("source_url", "").strip()
            if not url:
                url = f"local://{city_tag}/{slugify(event_data.get('title', ''))}-{event_data.get('date_start', '')}"
                event_data["source_url"] = url

            date_start = str(event_data.get("date_start") or "")[:10]
            title = event_data.get("title", "")
            norm_new = normalize_title(title)

            prio_new, prov_new = _get_url_priority(url)
            price_new = event_data.get("price_range", "")
            if "ticket_offers" not in event_data or not event_data["ticket_offers"]:
                event_data["ticket_offers"] = [{
                    "provider": prov_new,
                    "url": url,
                    "price": price_new,
                    "is_primary": True
                }]

            if url in existing_by_url:
                ex_id = existing_by_url[url][0]
                cursor.execute(
                    "UPDATE events SET payload = ?, date_start = ?, title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(event_data, ensure_ascii=False), date_start, title, ex_id)
                )
                continue

            merged = False
            if date_start in existing_by_date:
                for ex_item in existing_by_date[date_start]:
                    ex_id, ex_title, ex_payload_json = ex_item
                    norm_ex = normalize_title(ex_title)
                    similarity = SequenceMatcher(None, norm_new, norm_ex).ratio()

                    if norm_new == norm_ex or norm_new in norm_ex or norm_ex in norm_new or similarity >= 0.65:
                        ex_payload = json.loads(ex_payload_json)

                        desc_new = event_data.get("description", "")
                        desc_ex = ex_payload.get("description", "")
                        if desc_new and (not desc_ex or len(desc_new) > len(desc_ex)):
                            ex_payload["description"] = desc_new

                        img_new = event_data.get("image_url", "")
                        img_ex = ex_payload.get("image_url", "")
                        if img_new and ("/assets/thumbnails/" in img_new or not img_ex):
                            ex_payload["image_url"] = img_new

                        current_offers = ex_payload.get("ticket_offers") or []
                        if not current_offers and ex_payload.get("source_url"):
                            p_ex, pr_ex = _get_url_priority(ex_payload.get("source_url"))
                            current_offers = [{
                                "provider": pr_ex,
                                "url": ex_payload.get("source_url"),
                                "price": ex_payload.get("price_range", ""),
                                "is_primary": True
                            }]

                        incoming_offers = event_data.get("ticket_offers") or [{
                            "provider": prov_new,
                            "url": url,
                            "price": price_new,
                            "is_primary": False
                        }]

                        seen_u = {o.get("url") for o in current_offers if o.get("url")}
                        for inc in incoming_offers:
                            inc_u = inc.get("url")
                            if inc_u and inc_u not in seen_u:
                                current_offers.append(inc)
                                seen_u.add(inc_u)

                        current_offers.sort(key=lambda x: _get_url_priority(x.get("url", ""))[0], reverse=True)
                        for idx, o in enumerate(current_offers):
                            o["is_primary"] = (idx == 0)

                        ex_payload["ticket_offers"] = current_offers
                        if current_offers:
                            ex_payload["source_url"] = current_offers[0]["url"]
                            if current_offers[0].get("price"):
                                ex_payload["price_range"] = current_offers[0]["price"]

                        if len(title) < len(ex_title) and len(title) > 3:
                            ex_payload["title"] = title

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
            except sqlite3.IntegrityError:
                pass

        conn.commit()

def get_active_events(city_tag: str, min_date: str) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payload FROM events
            WHERE city_tag = ? AND COALESCE(NULLIF(json_extract(payload, '$.date_end'), ''), date_start) >= ?
            ORDER BY date_start ASC
        """, (city_tag, min_date))
        rows = cursor.fetchall()

        clean_records = []
        for r in rows:
            data = json.loads(r[0])
            clean_records.append(sanitize_payload(data))
        return clean_records


def sync_city_events(city_tag: str, deduplicated_events: list):
    """Zastępuje rekordy w bazie dla danego miasta przefiltrowanym, odduplikowanym zbiorem."""
    if not city_tag:
        return
    db_path = Path("data/events.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM events WHERE city_tag = ?", (city_tag,))
        for ev in deduplicated_events:
            ev_dict = ev.model_dump(mode='json') if hasattr(ev, 'model_dump') else (ev.dict() if hasattr(ev, 'dict') else ev)
            s_url = ev_dict.get("source_url", "")
            d_start = str(ev_dict.get("date_start", ev_dict.get("date", "")))[:10]
            title = ev_dict.get("title", "")
            payload_str = json.dumps(ev_dict, ensure_ascii=False)
            cursor.execute(
                """
                INSERT INTO events (city_tag, source_url, date_start, title, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (city_tag, s_url, d_start, title, payload_str)
            )
        conn.commit()
        print(f"[DB] Zsynchronizowano bazę dla '{city_tag}': zapisano {len(deduplicated_events)} unikalnych rekordów.")
    except Exception as e:
        conn.rollback()
        print(f"[DB ERROR] Błąd synchronizacji: {e}")
    finally:
        conn.close()



def purge_expired_events(city_tag: str):
    '''Twarde usunięcie przeterminowanych wydarzeń z bazy. Optymalizuje ETL.'''
    today_iso = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM events WHERE COALESCE(NULLIF(json_extract(payload, '$.date_end'), ''), date_start) < ? AND city_tag = ?", 
            (today_iso, city_tag)
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted
