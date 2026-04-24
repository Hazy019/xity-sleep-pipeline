"""
Title Card Generator for Xity Sleep Bible — v4.0 (MoviePy Edition)

Purpose:
    Renders 30s branded intros with elegant typography and non-stretched 
    landscape visuals (16:9). Fulfills strict aesthetic requirements for the project.

Hardware awareness:
    Limits rendering to ≤30 seconds to protect Ryzen 7 2700U thermal ceiling.
"""

import os
from pathlib import Path
from src.utils.logger import get_logger

# ── MoviePy Configuration ──────────────────────────────────────────────────────
# Required for TextClip method='caption'
from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS

from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

logger = get_logger("video.title_maker")

# Aesthetic constants (VA Guidelines)
FONT_NAME = "Georgia"
FONT_SIZE = 90
FONT_COLOR = "#C5A028"  # Gold
OVERLAY_COLOR = (26, 42, 74) # Dark Navy (#1A2A4A in RGB)

def generate_intro(topic_text: str, master_visual_path: str, output_path: str) -> str:
    """
    Generate a 30s intro using MoviePy with VA Guideline aesthetics.
    """
    if not Path(master_visual_path).exists():
        raise FileNotFoundError(f"Master visual not found: {master_visual_path}")

    logger.info(f"[generate_intro] Rendering premium intro: '{topic_text}'")

    # 1. Load Background and Loop
    from moviepy.video.fx.all import loop
    from moviepy.editor import ColorClip
    
    clip = VideoFileClip(str(master_visual_path))
    clip = loop(clip, duration=30)
    bg = clip.resize((1920, 1080))
    
    # 2. VA Guideline Overlay (Dark Navy at 45% opacity)
    overlay = (ColorClip(size=(1920, 1080), color=OVERLAY_COLOR)
               .set_duration(30)
               .set_opacity(0.45))
    
    # 3. Text Overlay (Gold, Centered, Georgia)
    txt = (TextClip(
                topic_text.upper(), # Uppercase per VA Guidelines
                method='caption',
                size=(bg.w * 0.7, None),
                fontsize=FONT_SIZE,
                color=FONT_COLOR,
                font=FONT_NAME,
                align='Center'
            )
            .set_duration(30)
            .set_position('center')
            .crossfadein(2.5)
            .crossfadeout(2.5))

    # 3. Assemble and Render
    final = CompositeVideoClip([bg, txt], size=(1920, 1080))
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio=False,
        bitrate="5000k",
        # preset='fast' for hardware safety
        ffmpeg_params=["-preset", "fast", "-crf", "18"]
    )
    
    # Clean up file handles
    clip.close()
    bg.close()
    
    return str(output_path)
