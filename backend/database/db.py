import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "plantpal.db")

def get_db_path():
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), env_path)
    return DB_PATH

@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    os.makedirs(os.path.dirname(get_db_path()), exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                plant_name  TEXT,
                last_scan   TEXT,
                last_city   TEXT
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                role            TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content         TEXT NOT NULL,
                intent          TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS scans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT,
                label           TEXT NOT NULL,
                confidence      REAL NOT NULL,
                weather_temp    REAL,
                weather_humidity REAL,
                weather_uv      REAL,
                weather_city    TEXT,
                diagnosis       TEXT,
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS weather_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                city        TEXT,
                lat         REAL,
                lon         REAL,
                temp        REAL,
                humidity    REAL,
                uv_index    REAL,
                cloud_cover INTEGER,
                fetched_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plant_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT,
                plant_name  TEXT NOT NULL,
                note        TEXT,
                health_score REAL,
                recorded_at TEXT NOT NULL
            );
        """)
    print("[db] Database initialised at:", get_db_path())

def save_message(session_id: str, role: str, content: str, intent: str = None):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions(id, created_at, updated_at) VALUES (?,?,?)",
            (session_id, now, now)
        )
        conn.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id)
        )
        conn.execute(
            "INSERT INTO conversations(session_id, role, content, intent, created_at) VALUES (?,?,?,?,?)",
            (session_id, role, content, intent, now)
        )

def get_history(session_id: str, limit: int = 20) -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
    rows.reverse()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def save_scan(session_id: str, label: str, confidence: float, weather: dict, diagnosis: str):
    now = datetime.utcnow().isoformat()
    w = weather or {}
    with get_db() as conn:
        conn.execute(
            """INSERT INTO scans
               (session_id, label, confidence, weather_temp, weather_humidity,
                weather_uv, weather_city, diagnosis, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (session_id, label, confidence,
             w.get("temp"), w.get("humidity"), w.get("uvIndex"),
             w.get("city"), diagnosis, now)
        )

def save_weather(lat: float, lon: float, data: dict):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO weather_logs(city, lat, lon, temp, humidity, uv_index, cloud_cover, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (data.get("city"), lat, lon, data.get("temp"), data.get("humidity"),
             data.get("uvIndex"), data.get("cloudCover"), now)
        )
