"""
10-Minute Video Builder for Xity Media Factory — v1.0
======================================================
Assembles the final 10-minute video from:
  1. TTS audio (.mp3)
  2. Multiple background video clips (scene-switching at word markers)
  3. Background music (.mp3 at 18% volume)
  4. Quote text overlays (word-timed fade-in/out)
  5. Chapter title cards (15s each)
"""

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

from src.utils.logger import get_logger
from src.utils.discord import notify
from src.gdrive_assets import get_background_path, get_music_path
from src.video.chapter_maker import generate_chapter_clips

logger = get_logger("video.builder_10min")

OUTPUTS_VIDEO = Path("outputs/video")
OUTPUTS_VIDEO.mkdir(parents=True, exist_ok=True)

TARGET_DURATION_SECS = 600  # 10 minutes exactly
FPS = 30
RESOLUTION = "1920:1080"


def build_10min_video(
    audio_path: str,
    metadata_path: str,
    chapters_path: str,
    date_str: str,
    chapter_bg_path: str | None = None,
) -> str:
    """
    Assemble the final 10-minute video.
    """
    logger.info("[builder_10min] START — 10-minute video assembly")
    notify("logs", "🎬 Starting 10-minute video assembly...")

    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    scene_schedule = metadata.get("scene_schedule", [])
    bg_music_file  = metadata.get("bg_music", "")
    quote_overlays = metadata.get("quote_overlays", [])

    # ── Step 1: Get the audio duration ───────────────────────────────────────
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    tts_duration = float(probe.stdout.strip())
    final_duration = min(tts_duration, TARGET_DURATION_SECS)
    logger.info(f"[builder_10min] TTS duration: {tts_duration:.1f}s | Using: {final_duration:.1f}s")

    # ── Step 2: Download assets from Drive ──────────────────────────────────
    backgrounds = {}
    for scene in scene_schedule:
        bg_file = scene["background"]
        if bg_file not in backgrounds:
            try:
                backgrounds[bg_file] = get_background_path(bg_file)
            except Exception as e:
                logger.warning(f"Could not get background {bg_file}: {e}. Falling back to fireplace.")
                backgrounds[bg_file] = get_background_path("Cozy_Fireplace_Looping_Video_Generation.mp4")

    music_path = None
    if bg_music_file:
        try:
            music_path = get_music_path(bg_music_file)
        except Exception as e:
            logger.warning(f"Could not get music {bg_music_file}: {e}")

    temp_dir = Path("outputs/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 3: Build Chapter Cards ──────────────────────────────────────────
    chapter_titles = json.loads(Path(chapters_path).read_text(encoding="utf-8"))
    chapter_card_paths = []
    if chapter_titles:
        logger.info(f"[builder_10min] Rendering {len(chapter_titles)} chapter cards...")
        # Use the first background for chapter cards
        first_bg = backgrounds.get(scene_schedule[0]["background"]) if scene_schedule else None
        if not first_bg:
            first_bg = get_background_path("Cozy_Fireplace_Looping_Video_Generation.mp4")
            
        chapter_card_paths = generate_chapter_clips(
            chapter_titles, 
            first_bg, 
            str(temp_dir / "chapters")
        )

    # ── Step 4: Build per-scene video segments using FFmpeg ─────────────────
    scene_clips = []
    
    # Word-to-time mapping
    WORDS_PER_MINUTE = 110
    WORDS_PER_SECOND = WORDS_PER_MINUTE / 60

    # Insert intro chapter card at the start
    if chapter_card_paths:
        scene_clips.append(chapter_card_paths[0])

    for idx, scene in enumerate(scene_schedule):
        at_word = scene["at_word"]
        next_word = scene_schedule[idx + 1]["at_word"] if idx + 1 < len(scene_schedule) else 999999

        start_time = at_word / WORDS_PER_SECOND
        end_time   = min(next_word / WORDS_PER_SECOND, final_duration)
        duration   = end_time - start_time

        if duration <= 0.5:
            continue

        bg_local  = backgrounds[scene["background"]]
        out_clip  = temp_dir / f"scene_{idx:02d}.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(bg_local),
            "-t", f"{duration:.3f}",
            "-vf", f"scale={RESOLUTION}:force_original_aspect_ratio=decrease,pad={RESOLUTION}:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-an",
            str(out_clip)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        scene_clips.append(str(out_clip))
        
        # Insert subsequent chapter cards at appropriate intervals (approx every 2 mins)
        # or we could match them to [CHAPTER] tags if we had word-indices for them.
        # For now, we'll just use the first card as intro.

    # ── Step 4: Concatenate scenes ───────────────────────────────────────────
    concat_list = temp_dir / "scene_concat.txt"
    # FFmpeg concat requires escaping or using forward slashes for absolute paths
    concat_lines = [f"file '{Path(c).absolute().as_posix()}'" for c in scene_clips]
    concat_list.write_text("\n".join(concat_lines), encoding="utf-8")

    raw_video = temp_dir / f"raw_video_{date_str}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(raw_video)
    ], check=True, capture_output=True)

    # ── Step 5: Mix audio ────────────────────────────────────────────────────
    mixed_audio = temp_dir / f"mixed_audio_{date_str}.mp3"
    if music_path:
        subprocess.run([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", str(music_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:a]volume=0.12,atrim=duration={final_duration}[bg];"
            f"[1:a]volume=1.0[voice];"
            f"[bg][voice]amix=inputs=2:duration=shortest[out]",
            "-map", "[out]",
            "-t", f"{final_duration:.3f}",
            str(mixed_audio)
        ], check=True, capture_output=True)
    else:
        mixed_audio = Path(audio_path)

    # ── Step 6: Combine ──────────────────────────────────────────────────────
    final_no_overlays = temp_dir / f"final_no_overlays_{date_str}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-i", str(mixed_audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(final_no_overlays)
    ], check=True, capture_output=True)

    # ── Step 7: Overlays ─────────────────────────────────────────────────────
    final_path = OUTPUTS_VIDEO / f"final_10min_{date_str}.mp4"

    if quote_overlays:
        drawtext_filters = []
        for i, ov in enumerate(quote_overlays):
            text      = ov["text"]
            at_word   = ov["at_word"]
            start_sec = at_word / WORDS_PER_SECOND
            end_sec   = start_sec + 8  # Show for 8 seconds

            # Write text to a file to avoid quoting/escaping hell
            quote_file = temp_dir / f"quote_{i}.txt"
            quote_file.write_text(text, encoding="utf-8")
            
            # Escape path for FFmpeg (Windows paths need special care in filters)
            q_path = str(quote_file.absolute()).replace("\\", "/").replace(":", "\\:")
            f_path = "C\\:/Windows/Fonts/georgia.ttf"

            dt = (
                f"drawtext=fontfile='{f_path}':"
                f"textfile='{q_path}':"
                f"fontcolor=white@0.9:fontsize=32:"
                f"x=(w-text_w)/2:y=h*0.8:"
                f"enable='between(t,{start_sec:.1f},{end_sec:.1f})':"
                f"shadowcolor=black@0.7:shadowx=2:shadowy=2"
            )
            drawtext_filters.append(dt)

        vf_string = ",".join(drawtext_filters)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(final_no_overlays),
            "-vf", vf_string,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy",
            str(final_path)
        ], check=True, capture_output=True)
    else:
        import shutil
        shutil.copy(str(final_no_overlays), str(final_path))

    return str(final_path)
