"""
Chapter Title Generator for Xity Sleep Bible — v1.0
Builds 15-second title cards used to separate prayer/meditation sections.
"""

import os
import PIL.Image
from pathlib import Path
from moviepy.config import change_settings

# ── Patch for Pillow 10.0+ ──────────────────────────────────────────────────
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS

# Verified ImageMagick path for this environment
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})

from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from src.utils.logger import get_logger

logger = get_logger("video.chapter_maker")

# Aesthetic Constants
RESOLUTION = (1920, 1080)   # Must match Base Block for -c copy stitching
DURATION = 15               # As requested
FONT_NAME = "Arial-Bold"
FONT_SIZE = 90              # Large for impact
COLOR = "white"
SHADOW_COLOR = "black"
STROKE_WIDTH = 2
FADE_SECS = 2

def generate_chapter_clips(titles, background_path, output_dir):
    """
    Generate 15s title clips for a list of strings.

    Args:
        titles (list[str]): List of chapter names (e.g. ["COURAGE IN CHRIST"]).
        background_path (str): Path to the looping background video.
        output_dir (str): Where to save the generated clips.

    Returns:
        list[str]: Paths to the generated .mp4 files.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    generated_paths = []

    if not Path(background_path).exists():
        raise FileNotFoundError(f"Background not found: {background_path}")

    logger.info(f"[chapter_maker] Rendering {len(titles)} chapter cards using {Path(background_path).name}")

    for i, title_data in enumerate(titles, start=1):
        output_path = out_dir / f"chapter_{i}.mp4"
        
        # Support both strings and dictionaries from the new JSON engine
        if isinstance(title_data, dict):
            title_text = title_data.get('title', 'Chapter')
        else:
            title_text = str(title_data)
            
        if output_path.exists():
            logger.info(f"[chapter_maker] Skipping {output_path.name} (already exists)")
            generated_paths.append(str(output_path))
            continue

        # 1. Load Background (16:9 1080p expected)
        # We loop/trim to 15s, then apply a gentle Ken Burns zoom
        from moviepy.video.fx.all import loop
        bg_clip = VideoFileClip(str(background_path))
        
        # Fixed aspect ratio: crop to 16:9 then resize to target RESOLUTION
        target_ratio = RESOLUTION[0] / RESOLUTION[1]
        source_ratio = bg_clip.w / bg_clip.h
        
        if source_ratio > target_ratio:
            # Source is wider than 16:9
            new_w = bg_clip.h * target_ratio
            bg_cropped = bg_clip.crop(x_center=bg_clip.w/2, width=new_w)
        else:
            # Source is taller than 16:9
            new_h = bg_clip.w / target_ratio
            bg_cropped = bg_clip.crop(y_center=bg_clip.h/2, height=new_h)
            
        bg = loop(bg_cropped, duration=DURATION).resize(RESOLUTION)
        
        # Zoom from 1.0x to 1.05x over 15 seconds
        bg_zoomed = bg.resize(lambda t: 1.0 + 0.0033 * t).set_position(('center', 'center'))

        # 1.5 Background Dimming Overlay
        # Darkens the background by 40% when the text is visible to make it pop
        from moviepy.editor import ColorClip
        dim = (ColorClip(size=RESOLUTION, color=(0,0,0))
               .set_opacity(0.4)
               .set_duration(DURATION)
               .crossfadein(FADE_SECS)
               .crossfadeout(FADE_SECS))

        # 2. Text Overlay (Georgia font, with drop shadow)
        # Shadow layer (offset by +4px X and Y, 60% opacity)
        txt_shadow = (TextClip(
                    str(title_text).upper(),
                    method='caption',
                    size=(RESOLUTION[0] * 0.7, None),
                    font='Georgia-Bold',
                    fontsize=FONT_SIZE,
                    color='black',
                    align='Center',
                    kerning=4
                )
                .set_opacity(0.6)
                .set_duration(DURATION)
                .crossfadein(FADE_SECS)
                .crossfadeout(FADE_SECS))
        
        # MoviePy center offset: we dynamically center it and then add +4 to x and y
        txt_shadow = txt_shadow.set_position(lambda t: (RESOLUTION[0]/2 - txt_shadow.w/2 + 4, RESOLUTION[1]/2 - txt_shadow.h/2 + 4))

        # Main text layer
        txt = (TextClip(
                    str(title_text).upper(),
                    method='caption',
                    size=(RESOLUTION[0] * 0.7, None),
                    font='Georgia-Bold',
                    fontsize=FONT_SIZE,
                    color=COLOR,
                    align='Center',
                    kerning=4
                )
                .set_duration(DURATION)
                .set_position('center')
                .crossfadein(FADE_SECS)
                .crossfadeout(FADE_SECS))

        # 3. Assemble
        final = CompositeVideoClip([bg_zoomed, dim, txt_shadow, txt], size=RESOLUTION)
        
        # 4. Render (Hardware safe settings)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio=False, # We use the pipeline-wide audio track
            fps=30,
            ffmpeg_params=["-preset", "fast", "-crf", "18"]
        )
        
        generated_paths.append(str(output_path))
        
        # Cleanup handles
        bg.close()
        final.close()

    logger.info(f"[chapter_maker] Completed {len(generated_paths)} clips.")
    return generated_paths
