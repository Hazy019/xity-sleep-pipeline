"""
Text-to-Speech conversion for Xity Sleep Bible.

Purpose:
    Convert a .txt meditation script to .mp3 using edge-tts.
    edge-tts is completely FREE — no API key, no account, no rate limits.
    It uses Microsoft Edge's neural TTS service under the hood.

Voice: en-US-ChristopherNeural  (warm, calm, adult male)
Rate:  -20%  (slower than default — breath-matched for sleep content)

Inputs:
    script_path (str): Path to the script .txt file.
    date_str (str):    YYYYMMDD string for output file naming.

Outputs:
    str: Path to generated .mp3 at outputs/audio/audio_{YYYYMMDD}.mp3

Error conditions:
    - Script file not found → FileNotFoundError (no retry)
    - edge-tts network failure → RuntimeError with instructions (retry 3×)
    - Output file missing or empty after synthesis → RuntimeError
"""

import asyncio
from datetime import datetime
from pathlib import Path

import edge_tts

from src.utils.discord import notify
from src.utils.logger import get_logger

logger = get_logger("audio.tts")

AUDIO_DIR = Path("outputs/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

VOICE  = "en-US-SteffanNeural"
RATE   = "-10%"
PITCH  = "-5Hz"
VOLUME = "+0%"


# ── Async TTS core ─────────────────────────────────────────────────────────────
async def _synthesise(text: str, output_path: str) -> None:
    """
    Run edge-tts synthesis and save the audio file.

    Purpose:
        Wraps edge_tts.Communicate in a coroutine so it can be driven
        by asyncio.run() from the synchronous pipeline.

    Args:
        text (str): Full meditation script text.
        output_path (str): Destination .mp3 file path.

    Error conditions:
        edge-tts exceptions propagate to asyncio.run() and up to generate_audio().
    """
    communicate = edge_tts.Communicate(
        text=text, 
        voice=VOICE, 
        rate=RATE, 
        pitch=PITCH, 
        volume=VOLUME
    )
    await communicate.save(output_path)


# ── Public entry point ─────────────────────────────────────────────────────────
def generate_audio(script_path: str, date_str: str | None = None) -> str:
    """
    Convert a meditation script .txt file to .mp3 using edge-tts (free, no key).

    Purpose:
        Reads the script, runs edge-tts synthesis at -20% rate using
        en-US-ChristopherNeural, validates the output file, and returns
        the path. Notifies Discord on start and completion.

    Args:
        script_path (str): Path to the .txt script file.
        date_str (str | None): YYYYMMDD string. Defaults to today.

    Returns:
        str: Path to the generated .mp3 file.

    Error conditions:
        - Script file not found → FileNotFoundError
        - Synthesis network error → RuntimeError with retry hint
        - Output file empty after synthesis → RuntimeError
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    script_file = Path(script_path)
    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    output_path = AUDIO_DIR / f"audio_{date_str}.mp3"

    logger.info(f"[generate_audio] START | voice={VOICE} | rate={RATE} | source={script_file.name}")
    notify("logs", f"🎙️ TTS started | `{VOICE}` @ `{RATE}` | source: `{script_file.name}`")

    text = script_file.read_text(encoding="utf-8")
    word_count = len(text.split())
    logger.info(f"[generate_audio] Input length: {word_count:,} words")

    try:
        asyncio.run(_synthesise(text, str(output_path)))
    except Exception as exc:
        msg = (
            f"edge-tts synthesis failed: {exc}\n"
            "Check your internet connection — edge-tts streams from Microsoft servers."
        )
        logger.error(f"[generate_audio] {msg}")
        notify("errors", f"🚨 TTS failure | {exc}", error_info=exc, ping_kyrell=True)
        raise RuntimeError(msg) from exc

    # ── Validate output ────────────────────────────────────────────────────────
    if not output_path.exists() or output_path.stat().st_size < 1_024:
        msg = f"TTS output missing or suspiciously small: {output_path}"
        logger.error(f"[generate_audio] {msg}")
        notify("errors", f"🚨 {msg}", ping_kyrell=True)
        raise RuntimeError(msg)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"[generate_audio] END | output={output_path} | size={size_mb:.1f} MB")
    notify("logs", f"✅ Audio generated | `audio_{date_str}.mp3` | {size_mb:.1f} MB")

    return str(output_path)
