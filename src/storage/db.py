"""
Minimalna SQLite evidencija vec obradjenih tendera - da dnevni pokretanja
ne dupliraju preuzimanje/notifikacije za isti tender. Koristi samo
standardnu biblioteku (bez dodatne zavisnosti).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from config import settings


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_tenders (
                tender_id TEXT PRIMARY KEY,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def is_seen(tender_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_tenders WHERE tender_id = ?", (tender_id,)
        ).fetchone()
        return row is not None


def mark_seen(tender_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_tenders (tender_id) VALUES (?)", (tender_id,)
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
