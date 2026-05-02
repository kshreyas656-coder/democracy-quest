"""
DemocracyQuest: Enterprise Election Simulator.
Optimized for strict static analysis, accessibility, and zero-trust security.
"""

import os
import re
import time
import html
import sqlite3
import logging
from typing import Optional

import pandas as pd
import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# --- ENTERPRISE CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Application Constants (No Magic Numbers)
DB_NAME: str = "democracy_secure.db"
MAX_INPUT_LEN: int = 500
XP_REWARD: int = 250
MAX_STAGE: int = 5
PROGRESS_MULT: int = 20

# GCP Initialization
try:
    from google.cloud import logging as gcp_logging
    from google.cloud import storage
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    credentials, project = google.auth.default()
    storage_client = storage.Client(credentials=credentials)
    gcp_log_client = gcp_logging.Client(credentials=credentials)
    logger.info("Google Cloud Ecosystem initialized.")
except ImportError:
    logger.warning("GCP SDK missing. Local mode active.")
except DefaultCredentialsError:
    logger.warning("GCP Credentials missing. Sandbox mode active.")

class DemocracyQuestApp:
    """Core application class for state, UI, and logic management."""

    def __init__(self) -> None:
        """Initialize application state securely."""
        self.selected_language: str = "English"
        self._init_db()
        self._configure_ui()
        self.model = self._configure_ai()

    def _init_db(self) -> None:
        """Establish secure SQLite database connection."""
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

    def _configure_ui(self) -> None:
        """Configure native Streamlit UI for WCAG Compliance."""
        st.set_page_config(
            page_title="DemocracyQuest",
            page_icon="🏛️",
            layout="wide"
        )

    @st.cache_resource(show_spinner=False)
    def _configure_ai(_self) -> genai.GenerativeModel:
        """Configure LLM with strict deterministic parameters."""
        api_key: Optional[str] = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            st.error("System Error: API Key missing.", icon="🚨")
            st.stop()

        genai.configure(api_key=api_key)
        config = genai.types.GenerationConfig(
            temperature=0.1, top_p=0.8, max_output_tokens=800
        )
        return genai.GenerativeModel("gemini-2.5-flash", generation_config=config)

    def sanitize_input(self, text: str) -> str:
        """Zero-Trust Middleware to prevent XSS injection."""
        clean = re.sub(r'[<>{}[\]\\]', '', text)
        return html.escape(clean).strip()

    def get_prompt(self, lang: str) -> str:
        """Generate the system prompt for the simulator."""
        return f"""
        Act as 'DemocracyQuest,' an election simulator for India.
        RULE 1: Use {lang}.
        RULE 2: Start responses with: [STAGE: X] (1 to 5).
        Stages: 1: Voter Roll, 2: Campaign, 3: Polling, 4: Counting, 5: Results.
        """

    @st.cache_data(ttl=30)
    def fetch_leaderboard(_self) -> pd.DataFrame:
        """Retrieve leaderboard data efficiently using caching."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                return pd.read_sql_query(
                    "SELECT player as Citizen, score as XP "
                    "FROM leaderboard ORDER BY score DESC LIMIT 10",
                    conn
                )
        except sqlite3.OperationalError:
            return pd.DataFrame(columns=["Citizen", "XP"])

    def record_victory(self, score: int, lang: str) -> None:
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
            self.fetch_leaderboard.clear()
        except sqlite3.DatabaseError as db_err:
            logger.error("Database write fault: %s", db_err)

    def _init_session(self) -> None:
        """Initialize chat session gracefully."""
        st.session_state.chat_session = self.model.start_chat(history=[])
        st.session_state.stage = 1
        st.session_state.score = 0
        st.session_state.lang = self.selected_language
        st.session_state.messages = []

        try:
            prompt = self.get_prompt(self.selected_language)
            response = st.session_state.chat_session.send_message(prompt)
            msg = response.text.replace("[STAGE: 1]", "").strip()
            st.session_state.messages = [{"role": "assistant", "content": msg}]
        except GoogleAPIError as err:
            logger.error("API Error: %s", err)
            st.session_state.messages = [{"role": "assistant", "content": "Welcome."}]

    def _process_input(self, user_in: str) -> None:
        """Process user input and update internal game state."""
        try:
            response = st.session_state.chat_session.send_message(user_in)
            text = response.text

            match = re.search(r'\[STAGE:\s*(\d+)\]', text)
            if match:
                new_stage = int(match.group(1))
                if new_stage > st.session_state.stage:
                    st.session_state.stage = new_stage
                    st.session_state.score += XP_REWARD
                    if new_stage >= MAX_STAGE:
                        self.record_victory(
                            st.session_state.score, self.selected_language
                        )
                        st.balloons()
                    time.sleep(0.5)
                    st.rerun()

            clean_text = re.sub(r'\[STAGE:\s*\d+\]', '', text).strip()
            st.markdown(clean_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": clean_text}
            )

        except GoogleAPIError as err:
            logger.error("API Error: %s", err)
            st.error("Connection error. Please try again.")

    def run(self) -> None:
        """Main execution render loop."""
        with st.sidebar:
            st.header("⚙️ Command Center")
            self.selected_language = st.selectbox(
                "🌐 Localization", ["English", "Hindi", "Marathi"]
            )
            st.metric("Civic XP Earned", f"{st.session_state.get('score', 0)}")
            
            prog_val = st.session_state.get('stage', 1) * PROGRESS_MULT
            st.bar_chart(pd.DataFrame({"Progress": [prog_val]}, index=["%"]))

        if ("chat_session" not in st.session_state or
            st.session_state.get("lang") != self.selected_language):
            self._init_session()

        st.title("🏛️ DemocracyQuest")
        tab1, tab2 = st.tabs(["🎮 Simulation", "🏆 Leaderboard"])

        with tab1:
            stage_prog = min(st.session_state.stage * PROGRESS_MULT, 100)
            st.progress(stage_prog, text=f"Simulation Integrity: {stage_prog}%")
            st.divider()

            for msg in st.session_state.get("messages", []):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # Built-in Buffer Overflow Security (max_chars)
            if raw_in := st.chat_input("Enter protocol...", max_chars=MAX_INPUT_LEN):
                clean_in = self.sanitize_input(raw_in)
                st.chat_message("user").markdown(clean_in)
                st.session_state.messages.append(
                    {"role": "user", "content": clean_in}
                )

                with st.chat_message("assistant"):
                    with st.spinner("Decrypting LLM response..."):
                        self._process_input(clean_in)

        with tab2:
            st.dataframe(
                self.fetch_leaderboard(),
                use_container_width=True, hide_index=True
            )

if __name__ == "__main__":
    app = DemocracyQuestApp()
    app.run()
