"""
Script generator for Stoic Media Factory — v11.0 (Modern Stoic Edition)
=========================================================================
Changes from v10:
  - Adapted for Stoic niche (Modern Stoicism & Dark Psychology)
  - Topic from topics.py bank (Stoic topics)
  - Calls Gemini Flash with the new Master Prompt v4.0
  - Parses [CHAPTER], [SCENE CHANGE], [PAUSE], [QUOTE] tags
  - No GDrive upload — assets are only DOWNLOADED from Drive
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from groq import Groq
from dotenv import load_dotenv
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from config.topics import TOPIC_BANK
from src.brain import log_generated, get_success_history, get_status
from src.utils.discord import notify
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger("script.generator")

SCRIPT_DIR = Path("outputs/scripts")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

_GEMINI_MODEL = "gemini-flash-latest"
_GROQ_FALLBACK = "llama-3.3-70b-versatile"

# ── Load master prompt from file ──────────────────────────────────────────────
def _load_master_prompt() -> str:
    p = Path("config/master_prompt_v3.txt")
    if p.exists():
        return p.read_text(encoding="utf-8")
    raise FileNotFoundError("config/master_prompt_v3.txt not found.")

# ── Pick next unused topic ────────────────────────────────────────────────────
def get_next_topic(manual_topic: str | None = None) -> dict:
    """
    Returns the next topic dict {topic, modern_struggle}.
    If manual_topic is given, find it in the bank.
    Otherwise, pick the first topic not in brain SUCCESS history.
    """
    if manual_topic:
        for t in TOPIC_BANK:
            if manual_topic.lower() in t["topic"].lower():
                return t
        return {"topic": manual_topic, "modern_struggle": "modern anxiety and discipline"}

    history = get_success_history(limit=50)
    used = {h["theme"] for h in history}
    for t in TOPIC_BANK:
        if t["topic"] not in used:
            return t

    logger.warning("[generator] All topics used — cycling from beginning")
    return TOPIC_BANK[0]

# ── LLM call ─────────────────────────────────────────────────────────────────
@retry(
    wait=wait_exponential(multiplier=1, min=6, max=60),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_llm(user_prompt: str, system_prompt: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and genai:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name=f"models/{_GEMINI_MODEL}",
                system_instruction=system_prompt
            )
            response = model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.8,
                    max_output_tokens=8192,
                )
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini failed: {e}. Trying Groq.")

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise EnvironmentError("No GEMINI_API_KEY or GROQ_API_KEY found in .env")

    client = Groq(api_key=groq_key)
    response = client.chat.completions.create(
        model=_GROQ_FALLBACK,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.8,
        max_tokens=8192,
    )
    return response.choices[0].message.content

# ── Parse JSON response ───────────────────────────────────────────────────────
def _parse_response(raw: str) -> dict:
    clean = raw.strip()
    try:
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        return json.loads(clean)
    except Exception as e:
        logger.error(f"[generator] Failed to parse LLM response: {e}")
        logger.error(f"[generator] Raw response: {raw}")
        raise

# ── Main generate function ────────────────────────────────────────────────────
def generate_script(
    manual_topic: str | None = None,
    date_str: str | None = None
) -> tuple[str, str, str, str]:
    """
    Generate all assets for a 10-minute faceless video.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    topic_data = get_next_topic(manual_topic)
    topic      = topic_data["topic"]
    struggle   = topic_data.get("modern_struggle", "modern anxiety")

    # Deduplication guard
    status = get_status(date_str, topic)
    if status == "SUCCESS":
        logger.info(f"[generator] Already posted: {topic} on {date_str}. Skipping.")
        notify("logs", f"ℹ️ Skipping — already posted: **{topic}** on {date_str}")
        raise RuntimeError(f"Topic '{topic}' already posted on {date_str}.")

    logger.info(f"[generator] START v11.0 | topic={topic} | struggle={struggle}")
    notify("queue", f"📝 Generating 10-min Stoic video | **{topic}**")

    history       = get_success_history(limit=5)
    recent_topics = [h["theme"] for h in history]
    system_prompt = _load_master_prompt()

    user_prompt = (
        f"Generate the complete 10-minute content package for YouTube.\n\n"
        f"TOPIC: {topic}\n"
        f"MODERN_STRUGGLE: {struggle}\n"
        f"RECENT_USED: {json.dumps(recent_topics)}\n\n"
        f"INSTRUCTION: Write the ACTUAL, FINAL script (1300-1500 words). Do NOT use placeholders.\n"
        f"CRITICAL: The 'script' field must be PURE NARRATION. No [BRACKETS], no tags, no scene names. Just the words to be spoken by the TTS engine. Use ellipses (...) and em dashes (—) for dramatic timing."
    )

    raw     = _call_llm(user_prompt, system_prompt)
    assets  = _parse_response(raw)

    # Save all outputs
    script_path   = SCRIPT_DIR / f"script_{date_str}.txt"
    chapters_path = SCRIPT_DIR / f"chapters_{date_str}.json"
    shorts_path   = SCRIPT_DIR / f"shorts_{date_str}.json"
    metadata_path = SCRIPT_DIR / f"metadata_{date_str}.json"

    script_path.write_text(assets["script"], encoding="utf-8")
    script_path.write_text(assets["script"], encoding="utf-8")
    chapters_path.write_text(json.dumps(assets.get("chapter_titles", []), indent=2), encoding="utf-8")
    shorts_path.write_text(json.dumps(assets.get("shorts_json", []), indent=2), encoding="utf-8")

    # Build full metadata payload
    metadata = {**assets.get("youtube_metadata", {})}
    metadata["bg_music"]         = assets.get("bg_music", "")
    metadata["scene_schedule"]   = assets.get("scene_schedule", [])
    metadata["quote_overlays"]   = assets.get("quote_overlays", [])  # Changed from scripture_overlays
    metadata["shorts_metadata"]  = assets.get("shorts_metadata", {})
    metadata["script_summary"]   = assets.get("script_summary", "")

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    wc = len(re.findall(r'\w+', assets["script"]))
    log_generated(date_str, topic, assets.get("script_summary", ""))
    logger.info(f"[generator] END | words={wc} | topic={topic}")
    notify("queue", f"✅ Script complete | **{wc} words** | **{topic}**")

    return str(script_path), str(chapters_path), str(shorts_path), str(metadata_path)
