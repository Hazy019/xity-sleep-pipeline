"""
Autonomous Brain for Xity Sleep Bible.

Purpose:
    Persistent memory for the AI. Handles topic deduplication by tracking
    every meditation script's theme and summary in a local SQLite database.
    Manages the PENDING → PROCESSING → SUCCESS lifecycle.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger("brain")

DB_PATH = Path("logs/brain.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _get_connection():
    """Returns a connection to the SQLite database with the schema initialized."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Initialize schema
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_str TEXT NOT NULL,
            theme TEXT NOT NULL,
            summary TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def get_success_history(limit: int = 10) -> list[dict]:
    """
    Retrieve the most recent successful or generated meditation topics.

    Args:
        limit (int): Number of recent records to fetch.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT date_str, theme, summary FROM history WHERE status IN ('SUCCESS', 'GENERATED') ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

def log_start(date_str: str, theme: str) -> None:
    """
    Record the start of a pipeline run. Sets status to PROCESSING.

    Args:
        date_str (str): YYYYMMDD string.
        theme (str): Name of the theme being processed.
    """
    with _get_connection() as conn:
        # Check if entry already exists (e.g. on resume)
        cursor = conn.execute(
            "SELECT id FROM history WHERE date_str = ? AND theme = ?",
            (date_str, theme)
        )
        row = cursor.fetchone()
        
        if row:
            conn.execute(
                "UPDATE history SET status = 'PROCESSING' WHERE id = ?",
                (row['id'],)
            )
            logger.debug(f"[brain] ID {row['id']} updated to PROCESSING")
        else:
            conn.execute(
                "INSERT INTO history (date_str, theme, status) VALUES (?, ?, 'PROCESSING')",
                (date_str, theme)
            )
            logger.info(f"[brain] Recorded new run starting: {date_str} ({theme})")
        conn.commit()

def log_generated(date_str: str, theme: str, summary: str) -> None:
    """
    Mark a run as GENERATED after script/audio/base-block are done.
    """
    with _get_connection() as conn:
        conn.execute(
            "UPDATE history SET status = 'GENERATED', summary = ? WHERE date_str = ? AND theme = ?",
            (summary, date_str, theme)
        )
        conn.commit()
    logger.info(f"[brain] Script GENERATED for {date_str} | {theme}")

def log_posted(date_str: str, theme: str) -> None:
    """
    Mark a run as SUCCESS (posted) after the final YouTube step.
    """
    with _get_connection() as conn:
        conn.execute(
            "UPDATE history SET status = 'SUCCESS' WHERE date_str = ? AND theme = ?",
            (date_str, theme)
        )
        conn.commit()
    logger.info(f"[brain] Pipeline SUCCESS (POSTED) for {date_str} | {theme}")

def get_status(date_str: str, theme: str) -> str | None:
    """Returns the current status of a given run/theme."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT status FROM history WHERE date_str = ? AND theme = ?",
            (date_str, theme)
        )
        row = cursor.fetchone()
        return row['status'] if row else None
