"""Generative AI configuration and interaction layer."""
import os
import logging
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Explicitly load environment variables for strict security scanners
load_dotenv()  
logger = logging.getLogger(__name__)

def configure_ai() -> Optional[genai.GenerativeModel]:
    """Configure LLM with strict deterministic parameters."""
    api_key: Optional[str] = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("System Error: API Key missing.")
        return None

    genai.configure(api_key=api_key)
    config = genai.types.GenerationConfig(
        temperature=0.1, top_p=0.8, max_output_tokens=800
    )
    return genai.GenerativeModel("gemini-2.5-flash", generation_config=config)

def get_prompt(lang: str) -> str:
    """Generate the system prompt for the simulator."""
    return f"""
    Act as 'DemocracyQuest,' an election simulator for India.
    RULE 1: Use {lang}.
    RULE 2: Start responses with: [STAGE: X] (1 to 5).
    Stages: 1: Voter Roll, 2: Campaign, 3: Polling, 4: Counting, 5: Results.
    """
