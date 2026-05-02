"""Test suite for modular DemocracyQuest architecture."""
import os
import sqlite3
import pytest
from unittest.mock import patch

import database
import ai_engine
import app

@pytest.fixture
def mock_db():
    """Provides isolated in-memory database context."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE leaderboard (
            id INTEGER PRIMARY KEY, player TEXT, score INTEGER, language TEXT
        )
    ''')
    conn.commit()
    # Monkeypatch the module variable for testing
    database.DB_NAME = ":memory:" 
    yield conn
    conn.close()

def test_sanitization() -> None:
    """Validate XSS injection prevention in UI layer."""
    assert "<script>" not in app.sanitize_input("<script>alert('x')</script>")

def test_db_write(mock_db) -> None:
    """Validate data persistence in DB layer."""
    database.record_victory(100, "English")
    cursor = mock_db.cursor()
    cursor.execute("SELECT score FROM leaderboard")
    assert cursor.fetchone()[0] == 100

@patch('database.sqlite3.connect')
def test_db_error_handling(mock_connect) -> None:
    """Validate graceful degradation on database connection failure."""
    mock_connect.side_effect = sqlite3.DatabaseError("Simulated Crash")
    database.init_db()  # Should handle error gracefully without crashing
    assert True

def test_missing_key(monkeypatch) -> None:
    """Validate AI Engine handles missing keys securely."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_engine.configure_ai() is None

def test_ai_prompt_generation() -> None:
    """Validate Prompt templating in AI Engine."""
    prompt = ai_engine.get_prompt("Marathi")
    assert "Marathi" in prompt
    assert "STAGE: X" in prompt
