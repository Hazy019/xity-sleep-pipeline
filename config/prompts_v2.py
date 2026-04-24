"""
Xity Sleep Bible — Master Content Engine v2.1 (Token-Efficient Edition)
======================================================================
Purpose: 
    Reduced token weight to fit within Groq/Gemini free-tier TPM limits.
    Maintains strict structural and aesthetic guidelines.
"""

import re
import json
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# SECURITY: Input sanitizer
# ─────────────────────────────────────────────────────────────────────────────
_INJECTION_RE = re.compile(r"ignore (previous|above|all)|disregard (previous|above|all)|you are now|new (system|role|task|instruction)|<\|.*?\|>|\[INST\]|###\s*(System|Human|Assistant)|```python", re.IGNORECASE)

def _sanitize(value: Any, field_name: str = "field") -> str:
    if value is None: return ""
    text = str(value).strip()
    if _INJECTION_RE.search(text):
        raise ValueError(f"[SECURITY] Injection pattern detected in '{field_name}'.")
    LIMITS = {"Theme Topic": 150, "Sleep Angle": 300, "First 15-Second Hook": 800, "Long Script Outline": 3000, "Description Draft": 3000}
    limit = LIMITS.get(field_name, 1500)
    return text[:limit] + "..." if len(text) > limit else text

# COMPRESSED SYSTEM PROMPT v2.2
_SYSTEM_PROMPT_v2 = r"""
Role: Content Engine for 'Xity Sleep Bible' (Christian Sleep Channel).
Format: STRICT JSON ONLY. NO PREAMBLE.

JSON Schema:
{
  "title": "Use provided 'Working Title Option 1' if available, otherwise: Sleep Bible Stories for Adults | [Theme] for Deep Peace (3 Hours)",
  "description": "CRITICAL: Use the provided 'Description Draft' as the foundation. Append chapter timestamps at the end. Formatting: draft text + \n\nCHAPTER TIMESTAMPS: \n00:00 - Title...",
  "tags": ["sleep meditation", "christian sleep", "anxiety relief", "scripture for sleep", "deep sleep", "insomnia relief", "sleep music", "relaxing music"],
  "thumbnail_text": "Use provided 'Thumbnail Text' if available, otherwise: [Theme] • Peace Tonight • 3 Hours",
  "pinned_comment": "Use provided 'Pinned Comment Option 1' if available.",
  "chapter_titles": [
    {"time": "00:00", "title": "Opening Prayer"},
    {"time": "20:00", "title": "The Storm Journey"},
    {"time": "2:50:00", "title": "Rest in God's Care"}
  ],
  "shorts_json": [
    {"start": 0.0, "end": 15.0, "text": "Use 'Shorts Caption Draft' as base for hook.", "zone": "A"}
  ],
  "script": "Write first 800 words here. Use slow cadence with ... pauses. Structure: S1: Welcome, S2: Intention, S3: Narrative start.",
  "background_file": "bg_jesus_calms_fear.mp4",
  "script_summary": "Summary of theme."
}

Rules: 
1. Use Navy #1A2A4A, Gold #C5A028 branding. 
2. Voice: SteffanNeural (-25% rate). 
3. Scripture: Focus on God's protection and peace.
4. If drafts are provided in the prompt, DO NOT ignore them. They are the primary instructions.
"""

def build_ingestion_prompt(row_data: dict, recent_themes: list[str] = None) -> tuple[str, str]:
    # Sanitize and extract all relevant instructions from Excel
    theme = _sanitize(row_data.get('Theme Topic', 'Untitled'), "Theme Topic")
    angle = _sanitize(row_data.get('Sleep Angle', 'Rest'), "Sleep Angle")
    hook = _sanitize(row_data.get('First 15-Second Hook', ''), "First 15-Second Hook")
    notes = _sanitize(row_data.get('VA Production Notes', ''), "VA Production Notes")
    
    # Drafts from Excel
    title_draft = _sanitize(row_data.get('Working Title Option 1', ''), "Working Title Option 1")
    desc_draft = _sanitize(row_data.get('Description Draft', ''), "Description Draft")
    thumb_draft = _sanitize(row_data.get('Thumbnail Text', ''), "Thumbnail Text")
    pinned_draft = _sanitize(row_data.get('Pinned Comment Option 1', ''), "Pinned Comment Option 1")
    shorts_draft = _sanitize(row_data.get('Shorts Caption Draft', ''), "Shorts Caption Draft")
    cta_draft = _sanitize(row_data.get('CTA Option 1', ''), "CTA Option 1")
    outline_draft = _sanitize(row_data.get('Long Script Outline', ''), "Long Script Outline")

    history_str = "\n".join([f"- {t}" for t in recent_themes]) if recent_themes else "None"
    
    user_prompt = f"""
INSTRUCTIONS FROM MASTER SCHEDULE:
- Theme: {theme}
- Sleep Angle: {angle}
- Title Draft: {title_draft}
- Description Draft: {desc_draft}
- Thumbnail Text Draft: {thumb_draft}
- Pinned Comment Draft: {pinned_draft}
- Shorts Hook Draft: {shorts_draft}
- CTA Draft: {cta_draft}
- Script Outline: {outline_draft}
- VA Production Notes: {notes}
- Hook (First 15s): {hook}

Recent History (Do not repeat themes):
{history_str}

Action: Generate the full JSON payload for this episode. 
IMPORTANT: Prioritize and copy the DRAFT content provided above into the corresponding JSON fields.
"""
    return _SYSTEM_PROMPT_v2, user_prompt

import logging
logger = logging.getLogger("config.prompts")

def parse_ingestion_response(raw_text: str) -> dict:
    """
    Resilient JSON parser that handles markdown blocks and partial truncation.
    """
    # 1. Try to find JSON within markdown blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    else:
        # 2. Try to find anything between the first { and last }
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        if start != -1 and end != -1:
            content = raw_text[start:end+1]
        else:
            content = raw_text

    # 3. Clean common LLM hallucinations
    content = content.replace("“", "\"").replace("”", "\"") # Smart quotes
    content = re.sub(r",\s*}", "}", content) # Trailing commas
    
    try:
        return json.loads(content, strict=False)
    except json.JSONDecodeError as e:
        # 4. Final attempt: Fix common truncation (missing closing quotes/braces)
        logger.warning(f"[parser] JSON decode failed, attempting surgery: {e}")
        
        # Try a series of aggressive closing patterns
        fixes = [
            "}", "\"}", " ]}", "\" ]}", " ]} }", "\" ]} }"
        ]
        for fix in fixes:
            try:
                return json.loads(content + fix)
            except: continue
        
        # 5. Last ditch: Extract what we can with regex if it's a total mess
        try:
            # If we just need the title and script to survive
            title_m = re.search(r'"title":\s*"(.*?)"', content)
            script_m = re.search(r'"script":\s*"(.*?)"', content, re.DOTALL)
            if title_m and script_m:
                logger.warning("[parser] EMERGENCY RECOVERY: Using regex extraction.")
                return {
                    "title": title_m.group(1),
                    "script": script_m.group(1),
                    "description": "Recovery mode - manual check required",
                    "tags": ["sleep"],
                    "thumbnail_text": title_m.group(1),
                    "chapter_titles": [{"time": "00:00", "title": "Opening"}],
                    "shorts_json": [],
                    "background_file": "bg_jesus_calms_fear.mp4",
                    "script_summary": "Recovered from partial failure"
                }
        except: pass
        
        raise ValueError(f"Bulletproof parse FAILED: {e}\nRaw start: {content[:200]}...")
