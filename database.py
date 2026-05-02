"""Secure database operations for DemocracyQuest."""
import sqlite3
import logging
import pandas as pd

logger = logging.getLogger(__name__)
DB_NAME = "democracy_secure.db"

def init_db() -> None:
    """Initialize the secure SQLite database."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leaderboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    language TEXT NOT NULL
                )
            ''')
            conn.commit()
    except sqlite3.DatabaseError as db_err:
        logger.error("Database initialization fault: %s", db_err)

def fetch_leaderboard() -> pd.DataFrame:
    """Retrieve leaderboard data efficiently."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return pd.read_sql_query(
                "SELECT player as Citizen, score as XP "
                "FROM leaderboard ORDER BY score DESC LIMIT 10",
                conn
            )
    except sqlite3.OperationalError:
        return pd.DataFrame(columns=["Citizen", "XP"])

def record_victory(score: int, lang: str) -> None:
    """Record user score securely using parameterized queries."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO leaderboard (player, score, language) "
                "VALUES (?, ?, ?)",
                ("Verified Citizen", score, lang)
            )
            conn.commit()
    except sqlite3.DatabaseError as db_err:
        logger.error("Database write fault: %s", db_err)
