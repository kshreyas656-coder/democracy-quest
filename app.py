"""
DemocracyQuest: Enterprise Election Simulator.
Modular architecture: UI Controller Layer.
"""
import re
import time
import html
import logging
import streamlit as st
import pandas as pd
from google.api_core.exceptions import GoogleAPIError

import database
import ai_engine

# --- ENTERPRISE CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_INPUT_LEN: int = 500
XP_REWARD: int = 250
MAX_STAGE: int = 5
PROGRESS_MULT: int = 20

# Initialize Subsystems
database.init_db()
model = ai_engine.configure_ai()

def sanitize_input(text: str) -> str:
    """Zero-Trust Middleware to prevent XSS injection."""
    clean = re.sub(r'[<>{}[\]\\]', '', text)
    return html.escape(clean).strip()

def init_session(lang: str) -> None:
    """Initialize chat session gracefully."""
    st.session_state.chat_session = model.start_chat(history=[]) if model else None
    st.session_state.stage = 1
    st.session_state.score = 0
    st.session_state.lang = lang
    st.session_state.messages = []

    if not model:
        st.error("System Error: AI Model failed to initialize. Check API Keys.", icon="🚨")
        st.stop()

    try:
        prompt = ai_engine.get_prompt(lang)
        response = st.session_state.chat_session.send_message(prompt)
        msg = response.text.replace("[STAGE: 1]", "").strip()
        st.session_state.messages = [{"role": "assistant", "content": msg}]
    except GoogleAPIError as err:
        logger.error("API Error: %s", err)
        st.session_state.messages = [{"role": "assistant", "content": "Welcome."}]

def process_input(user_in: str, lang: str) -> None:
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
                    database.record_victory(st.session_state.score, lang)
                    st.balloons()
                time.sleep(0.5)
                st.rerun()

        clean_text = re.sub(r'\[STAGE:\s*\d+\]', '', text).strip()
        st.markdown(clean_text)
        st.session_state.messages.append({"role": "assistant", "content": clean_text})
    except GoogleAPIError as err:
        logger.error("API Error: %s", err)
        st.error("Connection error. Please try again.")

def main() -> None:
    """Main UI execution loop."""
    st.set_page_config(page_title="DemocracyQuest", page_icon="🏛️", layout="wide")

    with st.sidebar:
        st.header("⚙️ Command Center")
        selected_language = st.selectbox("🌐 Localization", ["English", "Hindi", "Marathi"])
        st.metric("Civic XP Earned", f"{st.session_state.get('score', 0)}")
        prog_val = st.session_state.get('stage', 1) * PROGRESS_MULT
        st.bar_chart(pd.DataFrame({"Progress": [prog_val]}, index=["%"]))

    if "chat_session" not in st.session_state or st.session_state.get("lang") != selected_language:
        init_session(selected_language)

    st.title("🏛️ DemocracyQuest")
    tab1, tab2 = st.tabs(["🎮 Simulation", "🏆 Leaderboard"])

    with tab1:
        stage_prog = min(st.session_state.get('stage', 1) * PROGRESS_MULT, 100)
        st.progress(stage_prog, text=f"Simulation Integrity: {stage_prog}%")
        st.divider()

        for msg in st.session_state.get("messages", []):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if raw_in := st.chat_input("Enter protocol...", max_chars=MAX_INPUT_LEN):
            clean_in = sanitize_input(raw_in)
            st.chat_message("user").markdown(clean_in)
            st.session_state.messages.append({"role": "user", "content": clean_in})

            with st.chat_message("assistant"):
                with st.spinner("Decrypting LLM response..."):
                    process_input(clean_in, selected_language)

    with tab2:
        # Fetching directly from the isolated database module
        st.dataframe(database.fetch_leaderboard(), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
