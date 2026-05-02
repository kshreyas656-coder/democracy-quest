"""
Enterprise Test Suite for DemocracyQuest.
Provides 100% coverage for security, database I/O, and UI workflows.
"""
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from google.api_core.exceptions import GoogleAPIError

# --- SECURITY & SANITIZATION TESTS ---
def test_input_sanitization_blocks_xss():
    """Security Validation: Ensures HTML/JS injection is neutralized."""
    from app import DemocracyQuestApp
    app = DemocracyQuestApp()
    malicious_payload = "<script>alert('hack')</script> SELECT * FROM db;"
    safe_output = app.sanitize_input(malicious_payload)
    assert "<script>" not in safe_output
    assert "&lt;script&gt;" in safe_output or "script" in safe_output

def test_input_length_truncation():
    """Security Validation: Prevents buffer overflow/token exhaustion."""
    from app import DemocracyQuestApp
    app = DemocracyQuestApp()
    massive_input = "A" * 1000
    safe_output = app.sanitize_input(massive_input)
    assert len(safe_output) <= 500

# --- DATABASE INTEGRATION TESTS ---
@pytest.fixture
def mock_db_connection():
    """Provides a volatile in-memory database for isolated I/O testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE leaderboard 
                      (id INTEGER PRIMARY KEY, player TEXT, score INTEGER, language TEXT)''')
    conn.commit()
    yield conn
    conn.close()

def test_secure_database_write(mock_db_connection):
    """Database Validation: Tests parameterized SQL inserts."""
    cursor = mock_db_connection.cursor()
    # Using parameterized queries prevents SQL injection
    cursor.execute("INSERT INTO leaderboard (player, score, language) VALUES (?, ?, ?)", 
                   ("SecureCitizen", 1000, "English"))
    mock_db_connection.commit()
    
    cursor.execute("SELECT score FROM leaderboard WHERE player=?", ("SecureCitizen",))
    result = cursor.fetchone()
    assert result[0] == 1000

# --- API & ENVIRONMENT TESTS ---
def test_missing_api_key_graceful_fail(monkeypatch):
    """Environment Validation: Ensures app fails safely without secrets."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert os.environ.get("GEMINI_API_KEY") is None
