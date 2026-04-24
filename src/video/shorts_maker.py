"""
Professional Shorts Generator for Xity Sleep Bible — v2.0

WHAT CHANGED FROM v1.0:
────────────────────────────────────────────────────────────────────────────
v1.0 PROBLEMS:
  1. Font size 80px — too large. Chunks felt overwhelming, not peaceful.
  2. Single centered caption block — amateur. Pros use a two-zone layout.
  3. Georgia-Bold not available on all systems — random crashes.
  4. No silence at the start — first frame had text, reducing scroll-stop rate.
  5. No visual hierarchy — hook text looked identical to body text.
  6. crossfadein(0.2) too fast for a sleep meditation — jarring.

v2.0 SOLUTIONS:
  1. Font size 56px for body, 68px for hook — readable without screaming.
  2. TWO-ZONE CAPTION SYSTEM:
       Zone A (top-center, 15% down): The emotional hook — large, bold, white
       Zone B (bottom-center, 75% down): Body lines — smaller, softer weight
     This is exactly what Meditative Mind and Jason Stephenson use.
  3. Font fallback chain: tries Georgia-Bold → Arial-Bold → any system font.
  4. 1.5-second silent open — no text for the first 1.5s. Visual breathes.
     This single change increases average view time by letting the background
     land emotionally before words appear.
  5. Hook text is uppercase + tracked — CTA text is sentence-case + smaller.
     Visual hierarchy guides the eye and matches the emotional journey.
  6. crossfadein(0.5) / crossfadeout(0.5) — slow enough for sleep content.
  7. Darkening overlay (0.35 opacity) added when text is visible to ensure
     readability on any background brightness without covering the visual.

CAPTION ZONE LAYOUT (1080×1920):
  ┌────────────────────────────────┐
  │                                │  ← 0px to 288px: empty (visual breathes)
  │   [HOOK TEXT — Zone A]         │  ← ~288px (15% of 1920)
  │                                │
  │     [background visual]        │
  │                                │
  │   [body text — Zone B]         │  ← ~1440px (75% of 1920)
  │                                │
  └────────────────────────────────┘

CAPTION_DATA FORMAT (from generator.py Shorts prompt):
  [
    {"start": 0,  "end": 5,  "text": "CAN'T SLEEP TONIGHT?", "zone": "A"},
    {"start": 5,  "end": 10, "text": "Let this voice find you", "zone": "B"},
    {"start": 10, "end": 15, "text": "in the quiet...", "zone": "B"},
    ...
    {"start": 53, "end": 60, "text": "Full 3-hour meditation on the channel", "zone": "CTA"},
  ]

HARDWARE RULE:
  This module uses MoviePy which DOES re-encode every frame.
  It is ONLY called for the 60-second Short — never for long-form video.
  Thermal budget: ~45 seconds of encode time on Ryzen 7 2700U.
"""

import os
import sys
from pathlib import Path

import PIL.Image

# ── Pillow 10.0+ compatibility patch ──────────────────────────────────────────
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = getattr(PIL.Image, "Resampling", PIL.Image).LANCZOS

# ── ImageMagick path (required for MoviePy TextClip) ──────────────────────────
from moviepy.config import change_settings

_IMAGEMAGICK_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
if Path(_IMAGEMAGICK_PATH).exists():
    change_settings({"IMAGEMAGICK_BINARY": _IMAGEMAGICK_PATH})

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    VideoClip,
)

from src.utils.logger import get_logger

logger = get_logger("video.shorts_maker")

# ── Visual design tokens ───────────────────────────────────────────────────────
SHORT_W, SHORT_H = 1080, 1920          # Standard Shorts resolution

# Zone A: emotional hook — upper third, uppercase, large
HOOK_FONT_SIZE      = 110              # STOP THE SCROLL size
HOOK_Y_RATIO        = 0.15             # 15% from top
HOOK_COLOR          = "#C5A028"        # Gold
HOOK_STROKE_COLOR   = "black"
HOOK_STROKE_WIDTH   = 0.5              # Thin, premium stroke

# Zone B: body narration — lower third, sentence case, medium
BODY_FONT_SIZE      = 65
BODY_Y_RATIO        = 0.72             # 72% from top
BODY_COLOR          = "white"
BODY_STROKE_COLOR   = "black"
HOOK_STROKE_WIDTH   = 0.5
BODY_STROKE_WIDTH   = 2

# Zone CTA: call to action — bottom, smaller, gentle
CTA_FONT_SIZE       = 38
CTA_Y_RATIO         = 0.85
CTA_COLOR           = "white"

# Shared
CAPTION_WIDTH_PCT   = 0.82             # 82% of frame width
FADE_DURATION       = 0.5             # seconds — slow for sleep content
SILENT_OPEN_SECS    = 1.5             # no text for first 1.5s
OVERLAY_OPACITY     = 0.35            # darkening layer when text is visible

# Font fallback chain — tries each until one works
_FONT_CANDIDATES = ["Georgia-Bold", "Georgia", "Arial-Bold", "Arial", "DejaVu-Sans-Bold"]


def _get_working_font(size: int, test_text: str = "Test") -> str:
    """
    Try each font in _FONT_CANDIDATES and return the first one that renders
    without crashing. Falls back to the last candidate if all fail.

    Args:
        size (int): Font size for the test render.
        test_text (str): Text to try rendering.

    Returns:
        str: Name of a working font.
    """
    for font in _FONT_CANDIDATES:
        try:
            clip = TextClip(test_text, font=font, fontsize=size, color="white")
            clip.close()
            logger.debug(f"[_get_working_font] Using font: {font}")
            return font
        except Exception:
            continue
    logger.warning("[_get_working_font] All fonts failed — using last fallback")
    return _FONT_CANDIDATES[-1]


def _make_text_clip(
    text: str,
    font: str,
    font_size: int,
    color: str,
    stroke_color: str,
    stroke_width: int,
    y_ratio: float,
    start: float,
    end: float,
    frame_w: int = SHORT_W,
    frame_h: int = SHORT_H,
) -> TextClip:
    """
    Build a single caption TextClip with correct position, fade, and duration.

    Position is computed from y_ratio (0.0 = top, 1.0 = bottom) and centered
    horizontally. All captions have FADE_DURATION fade-in and fade-out.

    Args:
        text (str): Caption text.
        font (str): Font name.
        font_size (int): Font size in pixels.
        color (str): Text color.
        stroke_color (str): Stroke/shadow color.
        stroke_width (int): Stroke width in pixels.
        y_ratio (float): Vertical position ratio (0.0–1.0).
        start (float): Clip start time in seconds.
        end (float): Clip end time in seconds.
        frame_w (int): Frame width.
        frame_h (int): Frame height.

    Returns:
        TextClip: Positioned, timed, faded caption clip.
    """
    clip_w = int(frame_w * CAPTION_WIDTH_PCT)

    txt = (
        TextClip(
            text,
            method="caption",
            size=(clip_w, None),
            font=font,
            fontsize=font_size,
            color=color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            align="Center",
        )
        .set_start(start)
        .set_end(end)
        .crossfadein(FADE_DURATION)
        .crossfadeout(FADE_DURATION)
    )

    # Center horizontally, position vertically by ratio
    x_pos = (frame_w - txt.w) // 2
    y_pos = int(frame_h * y_ratio)
    txt = txt.set_position((x_pos, y_pos))

    return txt


def generate_short(
    audio_path: str,
    visual_path: str,
    captions_data: list,
    output_path: str,
) -> str:
    """
    Render a professional 60-second 9:16 YouTube Short with two-zone captions.

    Professional structure:
        0:00–0:01.5  Visual open — no text, background breathes
        0:01.5–0:50  Hook (Zone A) + body narration (Zone B) with fades
        0:50–1:00    CTA end card — gentle fade-in, smaller text

    Caption zones:
        Zone A ("A"):   Emotional hook — upper third, large, uppercase
        Zone B ("B"):   Body text — lower third, medium, sentence case
        Zone CTA ("CTA"): Call to action — very bottom, small, soft

    Args:
        audio_path (str): TTS .mp3 file (≥60 seconds). First 60s used.
        visual_path (str): 16:9 background .mp4. Center-cropped to 9:16.
        captions_data (list): List of dicts:
            [{"start": float, "end": float, "text": str, "zone": str}, ...]
            zone must be one of: "A", "B", "CTA"
        output_path (str): Output .mp4 path.

    Returns:
        str: Path to the rendered .mp4.

    Error conditions:
        - visual_path or audio_path missing → FileNotFoundError
        - MoviePy TextClip crash (font/ImageMagick issue) → logged + raised
    """
    for path, label in [(visual_path, "Visual"), (audio_path, "Audio")]:
        if not Path(path).exists():
            raise FileNotFoundError(f"{label} asset not found: {path}")

    logger.info(f"[generate_short] Starting render: {Path(output_path).name}")
    logger.info(f"[generate_short] Captions: {len(captions_data)} entries")

    # ── 1. Background: center crop 16:9 → 9:16, trim to 60s ─────────────────
    raw_clip   = VideoFileClip(str(visual_path))
    duration   = min(raw_clip.duration, 60.0)
    raw_clip   = raw_clip.subclip(0, duration)

    # Center crop to 9:16 without stretching
    target_w   = int(raw_clip.h * 9 / 16)
    x_offset   = max(0, (raw_clip.w - target_w) // 2)
    bg         = (
        raw_clip
        .crop(x1=x_offset, width=target_w)
        .resize((SHORT_W, SHORT_H))
    )

    # ── 2. Audio: first 60s of TTS ────────────────────────────────────────────
    voice_audio = AudioFileClip(str(audio_path)).subclip(0, duration)
    bg          = bg.set_audio(voice_audio)

    # ── 3. Resolve working fonts ──────────────────────────────────────────────
    hook_font = _get_working_font(HOOK_FONT_SIZE)
    body_font = _get_working_font(BODY_FONT_SIZE)
    cta_font  = _get_working_font(CTA_FONT_SIZE)

    # ── 4. Build caption clips ────────────────────────────────────────────────
    caption_clips  = []
    overlay_clips  = []  # darkening layers timed to text visibility

    for entry in captions_data:
        start = float(entry.get("start", 0))
        end   = float(entry.get("end",   start + 3))
        text  = str(entry.get("text", "")).strip()
        zone  = str(entry.get("zone", "B")).upper()

        # Enforce 1.5s silent open
        if end <= SILENT_OPEN_SECS:
            continue
        start = max(start, SILENT_OPEN_SECS)

        if not text or start >= end:
            continue

        if zone == "A":
            # Hook zone — uppercase, large, upper third
            txt_clip = _make_text_clip(
                text=text.upper(),
                font=hook_font,
                font_size=HOOK_FONT_SIZE,
                color=HOOK_COLOR,
                stroke_color=HOOK_STROKE_COLOR,
                stroke_width=HOOK_STROKE_WIDTH,
                y_ratio=HOOK_Y_RATIO,
                start=start,
                end=end,
            )
        elif zone == "CTA":
            # CTA zone — sentence case, small, very bottom, gentle
            txt_clip = _make_text_clip(
                text=text,
                font=cta_font,
                font_size=CTA_FONT_SIZE,
                color=CTA_COLOR,
                stroke_color="black",
                stroke_width=1,
                y_ratio=CTA_Y_RATIO,
                start=start,
                end=end,
            )
        else:
            # Zone B (default) — sentence case, medium, lower third
            txt_clip = _make_text_clip(
                text=text,
                font=body_font,
                font_size=BODY_FONT_SIZE,
                color=BODY_COLOR,
                stroke_color=BODY_STROKE_COLOR,
                stroke_width=BODY_STROKE_WIDTH,
                y_ratio=BODY_Y_RATIO,
                start=start,
                end=end,
            )

        caption_clips.append(txt_clip)

        # Add a subtle darkening overlay whenever text is on screen
        # This ensures readability on bright backgrounds
        dark = (
            ColorClip(size=(SHORT_W, SHORT_H), color=(0, 0, 0))
            .set_opacity(OVERLAY_OPACITY)
            .set_start(start)
            .set_end(end)
            .crossfadein(FADE_DURATION)
            .crossfadeout(FADE_DURATION)
        )
        overlay_clips.append(dark)

    # ── 5. Add Retention Progress Bar (NEW) ──────────────────────────────
    # A subtle 2px Gold bar at the bottom that fills as the video plays
    BAR_HEIGHT = 4 # slightly thicker for visibility
    BAR_COLOR = [197, 160, 40] # #C5A028 (Gold)
    
    import numpy as np
    def make_progress_frame(t):
        w = max(1, int((t / duration) * SHORT_W))
        frame = np.zeros((BAR_HEIGHT, SHORT_W, 3), dtype='uint8')
        frame[:, :w] = BAR_COLOR
        return frame
    
    progress_bar = (
        VideoClip(make_progress_frame, duration=duration)
        .set_start(0)
        .set_position(("left", "bottom"))
    )

    # ── 6. Composite and render ───────────────────────────────────────────────
    all_layers = [bg] + overlay_clips + caption_clips + [progress_bar]
    final      = CompositeVideoClip(all_layers, size=(SHORT_W, SHORT_H))

    logger.info(f"[generate_short] Rendering {len(caption_clips)} caption clips...")

    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=30,
        temp_audiofile=str(Path(output_path).parent / "temp_short_audio.m4a"),
        remove_temp=True,
        ffmpeg_params=["-preset", "fast", "-crf", "20"],
        logger=None,   # suppress MoviePy progress bar (use our logger instead)
    )

    # ── 6. Cleanup ────────────────────────────────────────────────────────────
    voice_audio.close()
    raw_clip.close()
    bg.close()
    final.close()
    for c in caption_clips + overlay_clips:
        c.close()

    logger.info(f"[generate_short] Done: {Path(output_path).name}")
    return str(output_path)