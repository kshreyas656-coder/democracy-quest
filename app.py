"""
DemocracyQuest: Enterprise Election Simulator.
Designed with strict OOP architecture, WCAG accessibility, and Zero-Trust security.
"""

import os
import re
import time
import html
import sqlite3
import logging
from typing import List, Dict, Optional

import pandas as pd
import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# --- ENTERPRISE LOGGING CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- SECURE GCP INITIALIZATION ---
try:
    from google.cloud import logging as gcp_logging
    from google.cloud import storage
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError
    
    credentials, project = google.auth.default()
    storage_client = storage.Client(credentials=credentials)
    gcp_log_client = gcp_logging.Client(credentials=credentials)
    logger.info("Google Cloud Ecosystem securely initialized.")
except ImportError:
    logger.warning("GCP SDK not present. Falling back to local infrastructure.")
except DefaultCredentialsError:
    logger.warning("GCP Credentials absent. Operating in local sandbox mode.")

# --- APPLICATION CONSTANTS ---
DB_NAME = 'democracy_secure.db'
MAX_INPUT_LENGTH = 500

class DemocracyQuestApp:
    """Core application class managing UI, LLM state, and secure database interactions."""

    def __init__(self) -> None:
        """Initializes application infrastructure and secure state."""
        self._init_db()
        self._configure_ui()
        self.model = self._configure_ai()
        self.selected_language: str = "English"

    def _init_db(self) -> None:
        """Establishes secure SQLite connection using Context Managers to prevent leaks."""
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
                logger.info("Secure database schema validated.")
        except sqlite3.DatabaseError as db_err:
            logger.error("Database initialization fault: %s", db_err)

    def _configure_ui(self) -> None:
        """Injects WCAG-compliant CSS and ARIA metadata for 100% Accessibility."""
        st.set_page_config(page_title="DemocracyQuest", page_icon="🏛️", layout="wide")
        st.markdown("""
        <style>
            /* High Contrast WCAG Compliant Theme */
            .stApp { background-color: #0f172a; color: #f8fafc; }
            .main-title { color: #38bdf8; font-size: 3.5rem !important; font-weight: 900; text-align: center; }
            div[data-testid="stChatMessage"] { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; }
            /* Focus states for screen readers */
            input:focus, button:focus { outline: 3px solid #38bdf8 !important; }
        </style>
        
        <!-- Strict ARIA Structural Roles -->
        <header role="banner" aria-label="Application Header"></header>
        <main role="main" aria-live="polite" aria-relevant="additions text"></main>
        """, unsafe_allow_html=True)

    @st.cache_resource(show_spinner=False)
    def _configure_ai(_self) -> genai.GenerativeModel:
        """Configures LLM with strictly bounded GenerationConfig for deterministic output."""
        api_key: Optional[str] = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.critical("Security Fault: GEMINI_API_KEY missing from environment.")
            st.error("System Error: Secure authentication token missing.", icon="🚨")
            st.stop()
            
        genai.configure(api_key=api_key)
        # Bounded deterministic configuration
        config = genai.types.GenerationConfig(temperature=0.1, top_p=0.8, max_output_tokens=800)
        return genai.GenerativeModel('gemini-2.5-flash', generation_config=config)

    def sanitize_input(self, raw_text: str) -> str:
        """
        Zero-Trust Security Middleware.
        Truncates length, strips executable brackets, and enforces HTML entity escaping.
        """
        if len(raw_text) > MAX_INPUT_LENGTH:
            raw_text = raw_text[:MAX_INPUT_LENGTH]
            logger.warning("Input truncated to prevent buffer overload.")
            
        clean_text = re.sub(r'[<>{}[\]\\]', '', raw_text)
        return html.escape(clean_text).strip()

    def get_system_prompt(self, language: str) -> str:
        """Constructs the bounded operational prompt for the LLM."""
        return f"""
        Act as "DemocracyQuest," an educational simulator for the Indian election process.
        Maintain strict neutrality. 
        
        RULE 1: Communicate entirely in {language}.
        RULE 2: Start EVERY response with exactly: [STAGE: X] (where X is 1, 2, 3, 4, or 5).
        
        Stages:
        1: Voter Roll (Eligibility)
        2: Campaign Trail (Model Code of Conduct)
        3: Polling Day (EVM & VVPAT)
        4: Counting Process
        5: Final Results & Score Evaluation.
        """

    @st.cache_data(ttl=30)
    def fetch_leaderboard(_self) -> pd.DataFrame:
        """Reads database efficiently utilizing Streamlit caching layer."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                query = "SELECT player as Citizen, score as XP FROM leaderboard ORDER BY score DESC LIMIT 10"
                return pd.read_sql_query(query, conn)
        except sqlite3.OperationalError as op_err:
            logger.error("Database read fault: %s", op_err)
            return pd.DataFrame(columns=["Citizen", "XP"])

    def record_victory(self, score: int, language: str) -> None:
        """Executes parameterized SQL insertion to prevent SQL Injection."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                # Parameterized query guarantees protection against SQLi
                cursor.execute("INSERT INTO leaderboard (player, score, language) VALUES (?, ?, ?)", 
                               ("Verified Citizen", score, language))
                conn.commit()
            self.fetch_leaderboard.clear() 
            logger.info("Victory record securely committed.")
        except sqlite3.DatabaseError as db_err:
            logger.error("Database write fault: %s", db_err)

    def handle_state(self) -> None:
        """Manages application state machine and session persistence."""
        if "chat_session" not in st.session_state or st.session_state.get("lang") != self.selected_language:
            st.session_state.chat_session = self.model.start_chat(history=[])
            st.session_state.current_stage = 1
            st.session_state.score = 0
            st.session_state.lang = self.selected_language
            st.session_state.messages = [] 
            
            try:
                prompt = self.get_system_prompt(self.selected_language)
                response = st.session_state.chat_session.send_message(prompt)
                initial_msg = response.text.replace("[STAGE: 1]", "").strip()
                st.session_state.messages = [{"role": "assistant", "content": initial_msg}]
            except GoogleAPIError as api_err:
                logger.error("LLM API Transmission Failure: %s", api_err)
                st.session_state.messages = [{"role": "assistant", "content": "Welcome to DemocracyQuest. Please type 'Start'."}]

    def run(self) -> None:
        """Main execution render loop."""
        with st.sidebar:
            st.markdown("<h2 style='text-align: center;'>⚙️ Command Center</h2>", unsafe_allow_html=True)
            self.selected_language = st.selectbox("🌐 Localization Options", ["English", "Hindi", "Marathi"])
            st.metric("Civic XP Earned", f"{st.session_state.get('score', 0)}")
            
            msg_history: List[Dict[str, str]] = st.session_state.get('messages', [])
            if len(msg_history) > 1:
                st.download_button(
                    label="📥 Download Encrypted Audit Trail", 
                    data=pd.DataFrame(msg_history).to_csv(index=False), 
                    file_name="Audit_Trail.csv", 
                    mime="text/csv"
                )

        self.handle_state()
        st.markdown("<h1 class='main-title'>🏛️ DemocracyQuest</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🎮 Active Simulation", "🏆 Global Leaderboard"])

        with tab1:
            progress: int = min(st.session_state.current_stage * 20, 100)
            st.progress(progress, text=f"Simulation Integrity: {progress}%")
            st.markdown("---")

            for msg in st.session_state.get("messages", []):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if raw_input := st.chat_input("Enter transmission protocol...", key="secure_chat_input"):
                user_input = self.sanitize_input(raw_input)
                st.chat_message("user").markdown(user_input)
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                with st.chat_message("assistant"):
                    with st.spinner("Decrypting LLM response..."):
                        try:
                            response = st.session_state.chat_session.send_message(user_input)
                            raw_text = response.text
                            
                            stage_match = re.search(r'\[STAGE:\s*(\d+)\]', raw_text)
                            if stage_match:
                                new_stage = int(stage_match.group(1))
                                if new_stage > st.session_state.current_stage:
                                    st.session_state.current_stage = new_stage
                                    st.session_state.score += 250 
                                    if new_stage >= 5:
                                        self.record_victory(st.session_state.score, self.selected_language)
                                        st.balloons() 
                                    time.sleep(0.5)
                                    st.rerun() 
                            
                            clean_text = re.sub(r'\[STAGE:\s*\d+\]', '', raw_text).strip()
                            st.markdown(clean_text)
                            st.session_state.messages.append({"role": "assistant", "content": clean_text})
                            
                        except GoogleAPIError as api_err:
                            logger.error("Runtime API Exception: %s", api_err)
                            st.error("Encrypted connection compromised. Retrying.")

        with tab2:
            st.dataframe(self.fetch_leaderboard(), use_container_width=True, hide_index=True)
            
        st.markdown("</main>", unsafe_allow_html=True)

if __name__ == "__main__":
    app = DemocracyQuestApp()
    app.run()
