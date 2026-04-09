"""
db.py
SQLite helpers for two tables:

1. event_log: every /predict call's input + output + timestamp.
   Pruned to last 90 days on every insert.

2. column_labels: static mapping of raw CSV column name -> human label.
   Populated once from studentlife_column_labels.csv.

Usage from main.py:
    from db import init_db, log_event, get_events, get_label, get_all_labels
    init_db()  # call once on startup
    log_event(user_text, evidence, posteriors)
    recent = get_events(days=7)
"""

import csv
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "uthryv.db"
LABELS_CSV = Path(__file__).parent.parent / "studentlife_column_labels.csv"
RETENTION_DAYS = 90


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if missing. Populate column_labels from CSV if empty."""
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT    NOT NULL,
                user_text  TEXT,
                evidence   TEXT    NOT NULL,
                posteriors TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_ts ON event_log(ts)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS column_labels (
                column_name TEXT PRIMARY KEY,
                label       TEXT NOT NULL
            )
        """)
        conn.commit()

        # Populate column_labels from CSV if table is empty
        count = conn.execute("SELECT COUNT(*) FROM column_labels").fetchone()[0]
        if count == 0 and LABELS_CSV.exists():
            with open(LABELS_CSV, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [(r["column"], r["label"]) for r in reader]
            conn.executemany(
                "INSERT OR REPLACE INTO column_labels (column_name, label) VALUES (?, ?)",
                rows,
            )
            conn.commit()
            print(f"Loaded {len(rows)} column labels from {LABELS_CSV.name}")
        elif count > 0:
            print(f"column_labels already populated ({count} rows)")
        else:
            print(f"WARNING: {LABELS_CSV} not found, column_labels empty")
    finally:
        conn.close()


def log_event(user_text: str | None, evidence: dict, posteriors: dict):
    """Insert a new event and prune rows older than RETENTION_DAYS."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO event_log (ts, user_text, evidence, posteriors) VALUES (?, ?, ?, ?)",
            (
                datetime.utcnow().isoformat(timespec="seconds"),
                user_text,
                json.dumps(evidence),
                json.dumps(posteriors),
            ),
        )
        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
        conn.execute("DELETE FROM event_log WHERE ts < ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()


def get_events(days: int = 7, limit: int = 500) -> list[dict]:
    """Return events from last `days` days, newest first."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, ts, user_text, evidence, posteriors
            FROM event_log
            WHERE ts >= ?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0],
            "ts": r[1],
            "user_text": r[2],
            "evidence": json.loads(r[3]),
            "posteriors": json.loads(r[4]),
        }
        for r in rows
    ]


def get_summaries(days: int = 7, limit: int = 50) -> list[dict]:
    """
    Return events from last `days` days where user_text (medical_summary) is non-empty.
    Newest first. Used by /explain to give the SLM recent context.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT ts, user_text
            FROM event_log
            WHERE ts >= ? AND user_text IS NOT NULL AND TRIM(user_text) != ''
            ORDER BY ts DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
    finally:
        conn.close()
    return [{"ts": r[0], "summary": r[1]} for r in rows]


def get_label(column_name: str) -> str | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT label FROM column_labels WHERE column_name = ?",
            (column_name,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def get_all_labels() -> dict[str, str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT column_name, label FROM column_labels").fetchall()
    finally:
        conn.close()
    return {r[0]: r[1] for r in rows}