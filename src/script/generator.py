"""
Script generator for Xity Sleep Bible — v10.0 (Flash 2.0 Edition)
=================================================================
Purpose:
    Generate 4,500+ word sleep meditation scripts using Gemini 2.0 Flash.
    Uses the stable SDK and a multi-part process to ensure volume and reliability.
"""

import logging
import os
import time
import json
import re
from datetime import datetime
from pathlib import Path
import warnings

# Suppress the SDK deprecation warning to keep logs clean
warnings.filterwarnings("ignore", category=FutureWarning)

# Stable SDK
try:
    import google.generativeai as genai
except ImportError:
    genai = None

from groq import Groq
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from config.prompts_v2 import build_ingestion_prompt, parse_ingestion_response
from src.utils.schedule_reader import get_row_for_date
from src.brain import log_generated, get_success_history
from src.utils.discord import notify
from src.utils.logger import get_logger
from src.scheduler import get_daily_topic

load_dotenv()

logger = get_logger("script.generator")

SCRIPT_DIR = Path("outputs/scripts")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

MIN_WORD_COUNT = 4_500
_GROQ_MODEL = "llama-3.3-70b-versatile"
_GROQ_MODEL_FALLBACK = "llama-3.1-8b-instant"
_GEMINI_MODEL = "gemini-1.5-flash-latest" 

_NARRATIVE_SYSTEM_PROMPT = (
    "You are the senior scriptwriter for Xity Sleep Bible. "
    "Your voice is calm, warm, and adult-friendly. "
    "Your task is to write immersive, scripture-centered meditation narratives. "
    "Use a slow, sleep-oriented cadence with frequent pauses (indicated by ...). "
    "Maintain high word counts by describing every scene and emotion in rich detail."
)

def _get_word_count(text: str) -> int:
    return len(re.findall(r'\w+', text))

@retry(
    wait=wait_exponential(multiplier=1, min=6, max=60),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_llm(user_prompt: str, system_prompt: str) -> str:
    """
    Call Gemini if available, otherwise fallback to Groq.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and genai:
        try:
            # Try both names as some versions/environments vary on the prefix
            m_name = _GEMINI_MODEL if _GEMINI_MODEL.startswith("models/") else f"models/{_GEMINI_MODEL}"
            
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name=m_name,
                system_instruction=system_prompt
            )
            response = model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.75,
                    max_output_tokens=8192,
                )
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini ({_GEMINI_MODEL}) failed: {e}. Falling back to Groq.")

    # 2. Attempt Groq
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise EnvironmentError("No API keys found.")

    client = Groq(api_key=groq_key)
    
    # TPM Safety: if combined prompt is massive, we must use 8B or trim
    combined_len = len(system_prompt) + len(user_prompt)
    model_to_use = _GROQ_MODEL
    if combined_len > 8000:
        logger.warning(f"Combined prompt too large ({combined_len} chars) for 70B. Using 8B.")
        model_to_use = _GROQ_MODEL_FALLBACK

    try:
        logger.info(f"[script.generator] Using Groq ({model_to_use})")
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.75,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        # Check for 429 (Rate Limit) specifically for Groq
        if "429" in str(e) and model_to_use == _GROQ_MODEL:
            logger.warning(f"Groq 70B Rate Limit (429) hit. Switching to 8B immediately.")
        elif model_to_use == _GROQ_MODEL:
            logger.warning(f"Groq 70B error: {e}. Trying 8B fallback.")
        else:
            raise
            
        # Fallback execution
        response = client.chat.completions.create(
            model=_GROQ_MODEL_FALLBACK,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.75,
            max_tokens=4096,
        )
        return response.choices[0].message.content

def generate_script(date_str: str | None = None) -> tuple[str, str, str, str]:
    """
    Multi-stage generator with Gemini 2.0 Flash support.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    try:
        # 1. Get the topic assignment (Client Request vs. VA Fallback)
        topic, is_client = get_daily_topic(date_str)
        
        # 2. Retrieve additional metadata if it's a client request
        if is_client:
            row_data = get_row_for_date(date_str)
        else:
            # Construct synthetic row data for the VA Niche volume increase.
            # IMPORTANT: Title MUST contain a US sleep phrase for the YouTube upload checklist.
            row_data = {
                'Theme Topic': topic,
                'Sleep Angle': "Productivity and Peace for Virtual Assistants",
                'Description Draft': (
                    f"The ultimate deep sleep meditation for Virtual Assistants. Relax your mind and body "
                    f"after a busy day with calming sleep music while we cover: {topic}. "
                    f"This 3-hour session is designed to help you fall asleep fast and wake up refreshed."
                ),
                'Working Title Option 1': f"{topic} | Deep Sleep Meditation for VAs (3 Hours)",
                'Thumbnail Text': f"VA GUIDE • {topic} • Deep Sleep"
            }
            
        theme_name = row_data.get('Theme Topic', 'Untitled')
        logger.info(f"[generate_script] START V10.0 | date={date_str} | theme={theme_name} | is_client={is_client}")

        # STAGE 1: Assets (Metadata, Chapters, Shorts)
        history = get_success_history(limit=3)
        system_prompt, user_prompt = build_ingestion_prompt(row_data, recent_themes=history)
        
        # TPM Optimization: if using Groq, we should use a shorter system prompt for Stage 1 if possible
        # But we need the Master Prompt rules for the JSON structure.
        
        logger.info("[generate_script] Stage 1: Initial assets...")
        raw_assets = _call_llm(user_prompt, system_prompt)
        assets = parse_ingestion_response(raw_assets)
        
        # Pacing for Rate Limits
        time.sleep(10)
        
        # STAGE 2: Narrative Expansion (3 Parts)
        logger.info("[generate_script] Stage 2: Narrative expansion...")
        parts = []
        # We split into 3 calls to ensure we hit the 4,500+ word goal
        narrative_targets = [
            "Part A: The Peaceful Evening & Rising Storm (1,500 words)",
            "Part B: The Awakening & 'Peace Be Still' (1,500 words)",
            "Part C: The Great Calm & Heart Application (1,500 words)"
        ]
        
        for i, target in enumerate(narrative_targets, 1):
            logger.info(f"[generate_script] Writing {target}...")
            p_prompt = (
                f"Continue the meditation script for '{theme_name}'.\n"
                f"Sleep Angle: {row_data.get('Sleep Angle', 'Deep Peace')}\n"
                f"Task: {target}\n"
                f"Instructions: Write a rich, slow-paced narrative. Describe the sounds, "
                f"the presence of Jesus, and the feelings of safety. Return ONLY text."
            )
            part_text = _call_llm(p_prompt, _NARRATIVE_SYSTEM_PROMPT)
            parts.append(part_text)
            time.sleep(10) # Pause between chapters
            
        # STAGE 3: Final assembly
        full_script = (
            f"{assets['script']}\n\n"
            f"[THE DEEP JOURNEY]\n\n" + 
            "\n\n".join(parts)
        )
        
        # Add concluding prayer if missing
        if "Amen" not in full_script[-1000:]:
            logger.info("[generate_script] Stage 3: Closing prayer...")
            prayer = _call_llm(
                f"Write a 500-word closing prayer and peaceful outro for '{theme_name}'.",
                _NARRATIVE_SYSTEM_PROMPT
            )
            full_script += f"\n\n{prayer}"

        # Save to Disk
        output_dir = SCRIPT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        script_path = output_dir / f"script_{date_str}.txt"
        chapters_path = output_dir / f"chapters_{date_str}.json"
        shorts_path = output_dir / f"shorts_{date_str}.json"
        metadata_path = output_dir / f"metadata_{date_str}.json"
        
        # Resiliently handle flat vs nested metadata
        if "youtube_metadata" in assets:
            metadata_payload = assets['youtube_metadata']
        else:
            # Flat schema from v2.1
            metadata_payload = {
                "title": assets.get("title", theme_name),
                "description": assets.get("description", ""),
                "tags": assets.get("tags", []),
                "thumbnail_text": assets.get("thumbnail_text", theme_name),
                "pinned_comment": assets.get("pinned_comment", "")
            }
            
        metadata_payload.update({
            'background_file': assets.get('background_file'),
            'shorts_metadata': assets.get('shorts_metadata') or {
                "title": f"{theme_name} | #SleepBible #Shorts",
                "description": assets.get("description", "")[:200]
            },
            'script_summary': assets.get('script_summary', '')
        })

        script_path.write_text(full_script, encoding="utf-8")
        chapters_path.write_text(json.dumps(assets.get('chapter_titles', []), indent=2), encoding="utf-8")
        shorts_path.write_text(json.dumps(assets.get('shorts_json', []), indent=2), encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata_payload, indent=2), encoding="utf-8")
        
        log_generated(date_str, theme_name, assets.get('script_summary', ''))
        
        word_count = _get_word_count(full_script)
        logger.info(f"[generate_script] END | Final words: {word_count}")
        notify("queue", f"✅ Pipeline V10.0 Complete | **{word_count} words** generated.")
        
        return str(script_path), str(chapters_path), str(shorts_path), str(metadata_path)

    except Exception as exc:
        logger.error(f"[generate_script] FAILED: {exc}")
        notify("errors", f"🚨 Scripting failed: {exc}", ping_kyrell=True)
        raise
