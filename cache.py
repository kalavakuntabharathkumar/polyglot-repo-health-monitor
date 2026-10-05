import sqlite3
from datetime import datetime, timezone


def open_cache(path='health_cache.sqlite'):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE IF NOT EXISTS health_cache ('
                 'key TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)')
    return conn


def cache_get(conn, key):
    row = conn.execute('SELECT payload FROM health_cache WHERE key = ?', (key,)).fetchone()
    return row[0] if row else None


def cache_set(conn, key, payload):
    timestamp = datetime.now(timezone.utc).isoformat()
    conn.execute('INSERT OR REPLACE INTO health_cache (key, payload, created_at) '
                 'VALUES (?, ?, ?)', (key, payload, timestamp))
    conn.commit()