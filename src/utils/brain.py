"""
Modern Stoic Pipeline — State Management Brain (SQLite)

Context:
    This module acts as the local database for the autonomous Python YouTube pipeline.
    It permanently records philosophy topics to ensure no topic is ever 
    generated or uploaded twice.

Hardware / Execution Safety:
    Uses standard built-in sqlite3. Lightweight, zero dependencies, and robust 
    against concurrent access if the system ever runs overlapping pipelines.

File structure:
    Stores data locally in outputs/stoic_brain.db so it persists across runs.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("core.brain")

# DB location — keeping it within outputs/ ensures it isn't reset by git ops easily
DB_DIR = Path("outputs")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "stoic_brain.db"


def _get_connection() -> sqlite3.Connection:
    """Returns a connected sqlite3 instance with row factory."""
    conn = sqlite3.connect(DB_PATH, isolation_level=None) # Autocommit ensures immediate locks
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """Create the topics table if it doesn't already exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create an index on status to make querying PENDING topics fast
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON topics(status)")


# Initialize the DB structure when the module is imported
_init_db()


def add_topics(topic_list: list[str]) -> int:
    """
    Bulk-adds new topics/verses into the brain. 
    
    Purpose: 
        Safely inserts a list of strings into the database. If a topic already
        exists in the brain, it is perfectly ignored via 'INSERT OR IGNORE'.
        
    Args:
        topic_list (list[str]): A list of string topics (e.g., ["Psalm 23", "John 3:16"])

    Returns:
        int: The number of new topics actually successfully added to the database.
    """
    if not topic_list:
        return 0

    inserted_count = 0
    with _get_connection() as conn:
        cursor = conn.cursor()
        for topic in topic_list:
            try:
                # INSERT OR IGNORE automatically skips duplicates based on the UNIQUE constraint
                cursor.execute(
                    "INSERT OR IGNORE INTO topics (topic, status) VALUES (?, 'PENDING')",
                    (topic,)
                )
                if cursor.rowcount > 0:
                    inserted_count += 1
            except sqlite3.Error as e:
                logger.error(f"[brain] Failed to insert topic '{topic}': {e}")
                
    logger.info(f"[brain] add_topics: Provided {len(topic_list)}, inserted {inserted_count} new.")
    return inserted_count


def get_next_topic() -> Optional[str]:
    """
    Retrieves exactly one "PENDING" topic for the pipeline to process, and locks it.
    
    Purpose:
        Fetches the oldest PENDING topic and immediately sets it to 'PROCESSING'.
        This locks the topic so that a second concurrent pipeline run won't grab
        the exact same topic while this one is rendering.
        
    Returns:
        str: The topic string. Back to main for script generation. 
             Returns None if the database is out of fresh topics.
    """
    with _get_connection() as conn:
        # Find the oldest pending topic
        cursor = conn.execute(
            "SELECT topic FROM topics WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1"
        )
        row = cursor.fetchone()
        
        if not row:
            logger.warning("[brain] get_next_topic: No PENDING topics remaining in database!")
            return None
            
        selected_topic = row["topic"]
        
        # Lock it immediately so it isn't picked up by any parallel/future executions
        conn.execute(
            "UPDATE topics SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP WHERE topic = ?",
            (selected_topic,)
        )
        
        logger.info(f"[brain] get_next_topic: Locked topic for PROCESSING -> {selected_topic}")
        return selected_topic


def mark_success(topic: str) -> None:
    """
    Updates the topic status to 'SUCCESS'.
    
    Purpose:
        Called at the very end of the pipeline when the YouTube API upload 
        returns a valid video ID. This permanently retires the topic.
        
    Args:
        topic (str): The exact topic string to mark successful.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            "UPDATE topics SET status = 'SUCCESS', updated_at = CURRENT_TIMESTAMP WHERE topic = ?",
            (topic,)
        )
        if cursor.rowcount == 0:
            logger.warning(f"[brain] mark_success: Topic '{topic}' not found in DB.")
        else:
            logger.info(f"[brain] mark_success: ✅ Topic perfectly finished -> {topic}")


def handle_error(topic: str, should_retry: bool = True) -> None:
    """
    Gracefully handles topic state if the pipeline crashes or times out.
    
    Purpose:
        If FFmpeg crashes or YouTube times out, the topic shouldn't permanently 
        be stuck as 'PROCESSING'. Either reset it back to 'PENDING' for a future 
        retry, or mark it as 'FAILED' if it's fundamentally broken.
        
    Args:
        topic (str): The topic string to update.
        should_retry (bool): If True, reverts to PENDING. If False, marks FAILED.
    """
    new_status = 'PENDING' if should_retry else 'FAILED'
    
    with _get_connection() as conn:
        cursor = conn.execute(
            "UPDATE topics SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE topic = ?",
            (new_status, topic)
        )
        if cursor.rowcount == 0:
            logger.warning(f"[brain] handle_error: Topic '{topic}' not found in DB.")
        else:
            logger.info(f"[brain] handle_error: 🚨 Reverted topic -> {topic} (New Status: {new_status})")
