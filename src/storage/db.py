"""
SQLite skladiste - jedini izvor istine za:
- tenders: svi prikupljeni tenderi (koristi ih i CLI i mobilni dashboard)
- app_settings: CPV kodovi / prag relevantnosti / pauza - menjaju se iz dashboard-a,
  bez potrebe za izmenom .env fajla ili restartom servera
- run_log: istorija pokretanja pretrage (za "Status" ekran u dashboard-u)

Koristi samo standardnu biblioteku (bez dodatne zavisnosti).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import settings

_DEFAULT_SETTINGS = {
    "cpv_codes": settings.CPV_CODES,
    "relevance_threshold": settings.RELEVANCE_THRESHOLD,
    "paused": False,
}


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenders (
                tender_id TEXT PRIMARY KEY,
                title TEXT,
                cpv_code TEXT,
                buyer TEXT,
                publish_date TEXT,
                deadline TEXT,
                detail_url TEXT,
                estimated_value TEXT,
                documents_json TEXT,
                relevance_score INTEGER,
                ai_summary TEXT,
                status TEXT DEFAULT 'collected',
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                tenders_found INTEGER DEFAULT 0,
                new_tenders INTEGER DEFAULT 0,
                error_message TEXT
            )
            """
        )
        for key, value in _DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )


# --- tenders -----------------------------------------------------------------

def upsert_tender(tender) -> None:
    """Prima src.collector.models.Tender i cuva/azurira ga u bazi."""
    documents = [
        {
            "dms_id": doc.dms_id,
            "file_name": doc.file_name,
            "download_url": doc.download_url,
            "local_path": doc.local_path,
            "extracted_chars": len(doc.extracted_text or ""),
        }
        for doc in tender.documents
    ]
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tenders (
                tender_id, title, cpv_code, buyer, publish_date, deadline,
                detail_url, estimated_value, documents_json, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'collected', ?)
            ON CONFLICT(tender_id) DO UPDATE SET
                title=excluded.title,
                buyer=excluded.buyer,
                deadline=excluded.deadline,
                estimated_value=excluded.estimated_value,
                documents_json=excluded.documents_json,
                updated_at=excluded.updated_at
            """,
            (
                tender.summary.tender_id,
                tender.summary.title,
                tender.summary.cpv_code,
                tender.summary.buyer,
                tender.summary.publish_date,
                tender.summary.deadline,
                tender.summary.detail_url,
                tender.estimated_value,
                json.dumps(documents),
                _now(),
            ),
        )


def get_tender(tender_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tenders WHERE tender_id = ?", (tender_id,)).fetchone()
        return _tender_row_to_dict(row) if row else None


def list_tenders(limit: int = 100, min_score: int | None = None) -> list[dict]:
    query = "SELECT * FROM tenders"
    params: list = []
    if min_score is not None:
        query += " WHERE relevance_score >= ?"
        params.append(min_score)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_tender_row_to_dict(row) for row in rows]


def count_tenders() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]


def _tender_row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["documents"] = json.loads(data.pop("documents_json") or "[]")
    return data


# --- app_settings --------------------------------------------------------------

def get_app_settings() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        result = {key: json.loads(value) for key, value in rows}
        for key, default in _DEFAULT_SETTINGS.items():
            result.setdefault(key, default)
        return result


def update_app_settings(
    cpv_codes: dict[str, str] | None = None,
    relevance_threshold: int | None = None,
    paused: bool | None = None,
) -> None:
    updates = {
        "cpv_codes": cpv_codes,
        "relevance_threshold": relevance_threshold,
        "paused": paused,
    }
    with _connect() as conn:
        for key, value in updates.items():
            if value is not None:
                conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, json.dumps(value)),
                )


# --- run_log ---------------------------------------------------------------------

def start_run() -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO run_log (started_at, status) VALUES (?, 'running')", (_now(),)
        )
        return cursor.lastrowid


def finish_run(
    run_id: int,
    status: str,
    tenders_found: int = 0,
    new_tenders: int = 0,
    error_message: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE run_log
            SET finished_at = ?, status = ?, tenders_found = ?, new_tenders = ?, error_message = ?
            WHERE id = ?
            """,
            (_now(), status, tenders_found, new_tenders, error_message, run_id),
        )


def get_last_run() -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM run_log ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def is_run_in_progress() -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM run_log WHERE status = 'running' LIMIT 1").fetchone()
        return row is not None


# --- helpers -----------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
