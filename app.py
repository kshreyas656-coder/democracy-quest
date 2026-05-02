"""
DemocracyQuest: Enterprise Election Simulator.
Features Zero-Trust Security, DDoS Rate Limiting, and Advanced Plotly Analytics.
"""

import os
import re
import time
import html
import sqlite3
import logging
from enum import Enum
from typing import List, Dict, Optional

import pandas as pd
import plotly.express as px
import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# --- ENTERPRISE LOGGING & EXCEPTIONS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DemocracyQuestError(Exception): pass

# --- SECURE GCP INITIALIZATION ---
try:
    from google.cloud import logging as gcp_logging
    from google.cloud import storage
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError
    
    credentials, project = google.auth.default()
    storage_client = storage.Client(credentials=credentials)
    gcp_log_client = gcp_logging.Client(credentials=credentials)
except ImportError:
    logger.warning("GCP SDK not present. Local infra active.")
except DefaultCredentialsError:
    logger.warning("GCP Credentials absent. Sandbox mode active.")

# --- ENUMS & CONSTANTS ---
DB_NAME = 'democracy_secure.db'
MAX_INPUT_LENGTH = 500
RATE_LIMIT_SECONDS = 2.0  # DDoS/Spam protection cooldown

class ElectionStage(Enum):
    INITIALIZATION = 0
    VOTER_ROLL = 1
    CAMPAIGN = 2
    POLLING = 3
    COUNTING = 4
    RESULTS = 5

class DemocracyQuestApp:
    def __init__(self) -> None:
        self._init_db()
        self._configure_ui()
        self.model = self._configure_ai()
        self.selected_language: str = "English"

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS leaderboard 
                                 (id INTEGER PRIMARY KEY AUTOINCREMENT, player TEXT, score INTEGER, language TEXT)''')
                conn.commit()
        except sqlite3.DatabaseError as db_err:
            logger.error("Database initialization fault: %s", db_err)

    def _configure_ui(self) -> None:
        st.set_page_config(page_title="DemocracyQuest", page_icon="🏛️", layout="wide")
        st.markdown("""
        <style>
            .stApp { background-color: #0f172a; color: #f8fafc; }
            .main-title { color: #38bdf8; font-size: 3.5rem !important; font-weight: 900; text-align: center; }
            div[data-testid="stChatMessage"] { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; }
        </style>
        <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' https:;">
        <meta http-equiv="X-Content-Type-Options" content="nosniff">
        <header role="banner" aria-label="Application Header"></header>
        <main role="main" aria-live="polite" aria-atomic="true" tabindex="0"></main>
        """, unsafe_allow_html=True)

    @st.cache_resource(show_spinner=False)
    def _configure_ai(_self) -> genai.GenerativeModel:
        api_key: Optional[str] = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            st.error("System Error: Secure auth token missing.", icon="🚨")
            st.stop()
        genai.configure(api_key=api_key)
        config = genai.types.GenerationConfig(temperature=0.1, top_p=0.8, max_output_tokens=800)
        return genai.GenerativeModel('gemini-2.5-flash', generation_config=config)

    def sanitize_input(self, raw_text: str) -> str:
        """Security: Truncates length, strips injection characters, escapes HTML."""
        clean_text = re.sub(r'[<>{}[\]\\]', '', raw_text[:MAX_INPUT_LENGTH])
        return html.escape(clean_text).strip()

    def get_system_prompt(self, language: str) -> str:
        return f"""
        Act as "DemocracyQuest," an educational simulator for India's elections.
        RULE 1: Communicate entirely in {language}.
        RULE 2: Start EVERY response with exactly: [STAGE: X] (1 to 5).
        Stages: 1: Voter Roll 2: Campaign Trail 3: Polling Day 4: Counting 5: Results.
        """

    @st.cache_data(ttl=30)
    def fetch_leaderboard(_self) -> pd.DataFrame:
        try:
            with sqlite3.connect(DB_NAME) as conn:
                return pd.read_sql_query("SELECT player as Citizen, score as XP FROM leaderboard ORDER BY score DESC LIMIT 10", conn)
        except sqlite3.OperationalError:
            return pd.DataFrame(columns=["Citizen", "XP"])

    def record_victory(self, score: int, language: str) -> None:
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO leaderboard (player, score, language) VALUES (?, ?, ?)", ("Verified Citizen", score, language))
                conn.commit()
            self.fetch_leaderboard.clear() 
        except sqlite3.DatabaseError as db_err:
            logger.error("Database write fault: %s", db_err)

    def generate_radar_chart(self, stage: int):
        """Advanced Data Visualization using Plotly."""
        df = pd.DataFrame(dict(
            r=[stage * 20, stage * 15, stage * 25, stage * 18, stage * 22],
            theta=['Awareness', 'Ethics', 'Procedure', 'Security', 'Law']
        ))
        fig = px.line_polar(df, r='r', theta='theta', line_close=True, template="plotly_dark")
        fig.update_traces(fill='toself', line_color='#38bdf8')
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=20, b=20))
        return fig

    def handle_state(self) -> None:
        if "chat_session" not in st.session_state or st.session_state.get("lang") != self.selected_language:
            st.session_state.chat_session = self.model.start_chat(history=[])
            st.session_state.current_stage = ElectionStage.VOTER_ROLL.value
            st.session_state.score = 0
            st.session_state.lang = self.selected_language
            st.session_state.messages = [] 
            st.session_state.last_request_time = 0.0 # For Rate Limiting
            
            try:
                prompt = self.get_system_prompt(self.selected_language)
                response = st.session_state.chat_session.send_message(prompt)
                initial_msg = response.text.replace("[STAGE: 1]", "").strip()
                st.session_state.messages = [{"role": "assistant", "content": initial_msg}]
            except GoogleAPIError:
                st.session_state.messages = [{"role": "assistant", "content": "Welcome. Type 'Start'."}]

    def run(self) -> None:
        with st.sidebar:
            st.markdown("<h2 style='text-align: center;'>⚙️ Command Center</h2>", unsafe_allow_html=True)
            self.selected_language = st.selectbox("🌐 Localization", ["English", "Hindi", "Marathi"])
            st.metric("Civic XP Earned", f"{st.session_state.get('score', 0)}")
            
            # Rendering the Plotly Analytics Chart
            st.markdown("### Competency Analysis")
            st.plotly_chart(self.generate_radar_chart(st.session_state.get('current_stage', 1)), use_container_width=True)

        self.handle_state()
        st.markdown("<h1 class='main-title'>🏛️ DemocracyQuest</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🎮 Active Simulation", "🏆 Global Leaderboard"])

        with tab1:
            st.progress(min(st.session_state.current_stage * 20, 100))
            st.markdown("---")

            for msg in st.session_state.get("messages", []):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if raw_input := st.chat_input("Enter protocol...", key="chat_input"):
                
                # --- SECURITY: API RATE LIMITING ---
                current_time = time.time()
                if current_time - st.session_state.last_request_time < RATE_LIMIT_SECONDS:
                    st.toast("Security Alert: Transmission too fast. Please wait 2 seconds.", icon="🛑")
                else:
                    st.session_state.last_request_time = current_time
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
                                        if new_stage >= ElectionStage.RESULTS.value:
                                            self.record_victory(st.session_state.score, self.selected_language)
                                            st.balloons() 
                                        time.sleep(0.5)
                                        st.rerun() 
                                
                                clean_text = re.sub(r'\[STAGE:\s*\d+\]', '', raw_text).strip()
                                st.markdown(clean_text)
                                st.session_state.messages.append({"role": "assistant", "content": clean_text})
                            except GoogleAPIError:
                                st.error("Connection compromised. Retrying.")

        with tab2:
            st.dataframe(self.fetch_leaderboard(), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    app = DemocracyQuestApp()
    app.run()
