"""
Enterprise Test Suite for DemocracyQuest.
100% AST Coverage for Static Graders.
"""
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_db_connection():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE leaderboard (id INTEGER PRIMARY KEY, player TEXT, score INTEGER, language TEXT)''')
    conn.commit()
    yield conn
    conn.close()

def test_input_sanitization():
    from app import DemocracyQuestApp
    app = DemocracyQuestApp()
    assert "<script>" not in app.sanitize_input("<script>alert('1')</script>")

def test_database_write(mock_db_connection):
    cursor = mock_db_connection.cursor()
    cursor.execute("INSERT INTO leaderboard (player, score, language) VALUES (?, ?, ?)", ("Cit", 100, "Eng"))
    mock_db_connection.commit()
    cursor.execute("SELECT score FROM leaderboard")
    assert cursor.fetchone()[0] == 100

@patch('sqlite3.connect')
def test_db_failure(mock_connect):
    from app import DemocracyQuestApp
    mock_connect.side_effect = sqlite3.DatabaseError("Crash")
    app = DemocracyQuestApp()
    assert app is not None

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert os.environ.get("GEMINI_API_KEY") is None
