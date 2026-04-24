"""
Shorts Strategist for Xity Sleep Bible.
Extracts 1 high-impact Short from a long-form meditation script.
"""

import json
import os
import re
from pathlib import Path
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

from config.prompts import MASTER_SYSTEM_PROMPT
from src.utils.logger import get_logger

logger = get_logger("script.shorts_strategist")

_GROQ_MODEL = "llama-3.1-8b-instant" # Temporarily using fast model for testing

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _call_groq_json(prompt: str) -> list:
    """
    Calls Groq and ensures the output is valid JSON.
    """
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        response_format={"type": "json_object"} if "llama-3.3" in _GROQ_MODEL else None
    )

    content = response.choices[0].message.content
    
    # If not using json_object mode, try to extract JSON block
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif content.strip().startswith("[") or content.strip().startswith("{"):
        pass
    else:
        # Fallback regex
        match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
        if match:
            content = match.group(0)

    data = json.loads(content)
    # The prompt asks for SHORT [N] headers but also a JSON block.
    # If the LLM returned a dict with keys like "SHORT 1", we normalize it.
    if isinstance(data, dict):
        shorts = []
        for key in sorted(data.keys()):
            if "SHORT" in key.upper():
                shorts.append(data[key])
        if shorts:
            return shorts
        return [data] # Maybe it's just one short or the whole list as one object
    
    return data

def extract_shorts(script_path: str, date_str: str) -> str:
    """
    Reads a script and uses Groq to extract 3 Shorts JSON.
    Saves to outputs/scripts/shorts_{date_str}.json
    """
    script_text = Path(script_path).read_text(encoding="utf-8")
    
    # Truncate script to stay within TPM/Context limits (approx 2000 words is plenty for shorts)
    truncated_script = " ".join(script_text.split()[:2000])
    prompt = f"Generate 1 high-impact Short script from the following meditation text. Return exactly JSON following the OUTPUT CONTRACT — SHORTS SCRIPT.\n\nSCRIPT:\n{truncated_script}"

    logger.info(f"[extract_shorts] Calling Groq for 1 Short | date={date_str}")
    
    try:
        shorts_data = _call_groq_json(prompt)
        
        # Validation: Ensure we have at least 1 short
        if len(shorts_data) < 1:
            logger.warning(f"[extract_shorts] Expected 1 short, got {len(shorts_data)}. Attempting to continue.")

        output_path = Path("outputs/scripts") / f"shorts_{date_str}.json"
        output_path.write_text(json.dumps(shorts_data, indent=2), encoding="utf-8")
        
        logger.info(f"[extract_shorts] Saved Shorts JSON: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"[extract_shorts] Failed: {e}")
        raise
