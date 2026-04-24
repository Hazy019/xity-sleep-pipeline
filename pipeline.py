"""
Stoic Media Factory — Main Pipeline v11.0 (Modern Stoic Edition)
==================================================================
Usage:
    python pipeline.py                        # Auto-select next unused topic
    python pipeline.py --topic "Marcus Aurelius"
    python pipeline.py --dry-run              # Generate script only
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.brain import log_start, log_posted, get_status
from src.generator import generate_script
from src.audio.tts import generate_audio
from src.video.builder_10min import build_10min_video
from src.video.shorts_maker import generate_short
from src.publish.youtube_10min import upload_video
from src.gdrive_assets import sync_assets
from src.utils.cleanup import cleanup_temp, purge_old_outputs
from src.utils.discord import notify
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger("pipeline")


def run(
    topic: str | None = None,
    date_str: str | None = None,
    dry_run: bool = False,
    start_step: int = 1,
    privacy: str = "public",
):
    date_str = date_str or datetime.now().strftime("%Y%m%d")
    logger.info(f"[pipeline] START v11.0 | date={date_str} | dry_run={dry_run}")
    notify("queue", f"🚀 Stoic Pipeline v11.0 started | date={date_str}")

    # ── STEP 1: Sync Assets ──────────────────────────────────────────────────
    if start_step <= 1:
        logger.info("[pipeline] Step 1: Syncing GDrive assets...")
        sync_assets()

    # ── STEP 2: Generate Script ──────────────────────────────────────────────
    script_path = chapters_path = shorts_path = metadata_path = None
    if start_step <= 2:
        logger.info("[pipeline] Step 2: Generating script...")
        script_path, chapters_path, shorts_path, metadata_path = generate_script(
            manual_topic=topic, date_str=date_str
        )
        meta = json.loads(Path(metadata_path).read_text())
        theme = meta.get("title", "Unknown Topic")
        log_start(date_str, theme)
    else:
        script_dir = Path("outputs/scripts")
        script_path   = str(script_dir / f"script_{date_str}.txt")
        chapters_path = str(script_dir / f"chapters_{date_str}.json")
        shorts_path   = str(script_dir / f"shorts_{date_str}.json")
        metadata_path = str(script_dir / f"metadata_{date_str}.json")

    if dry_run:
        logger.info("[pipeline] DRY RUN — stopping after script generation.")
        return

    # ── STEP 3: TTS ──────────────────────────────────────────────────────────
    audio_path = None
    if start_step <= 3:
        logger.info("[pipeline] Step 3: TTS generation...")
        audio_path = generate_audio(script_path, date_str)
    else:
        audio_path = f"outputs/audio/audio_{date_str}.mp3"

    # ── STEP 4: Video Build ──────────────────────────────────────────────────
    video_path = None
    if start_step <= 4:
        logger.info("[pipeline] Step 4: Building 10-minute video...")
        video_path = build_10min_video(
            audio_path=audio_path,
            metadata_path=metadata_path,
            chapters_path=chapters_path,
            date_str=date_str,
        )
    else:
        video_path = f"outputs/video/final_10min_{date_str}.mp4"

    # ── STEP 5: YouTube Short ────────────────────────────────────────────────
    short_path = None
    if start_step <= 5:
        logger.info("[pipeline] Step 5: Building Short...")
        from src.gdrive_assets import get_background_path
        meta_data = json.loads(Path(metadata_path).read_text())
        first_bg  = meta_data.get("scene_schedule", [{}])[0].get("background", "")
        bg_path   = get_background_path(first_bg) if first_bg else video_path
        shorts_data = json.loads(Path(shorts_path).read_text())
        short_path  = f"outputs/video/short_{date_str}.mp4"
        generate_short(
            audio_path=audio_path,
            visual_path=bg_path,
            captions_data=shorts_data,
            output_path=short_path,
        )
    else:
        short_path = f"outputs/video/short_{date_str}.mp4"

    # ── STEP 6: Upload Long-form ─────────────────────────────────────────────
    if start_step <= 6:
        logger.info(f"[pipeline] Step 6: Uploading to YouTube (privacy={privacy})...")
        video_id = upload_video(video_path, metadata_path, privacy=privacy)

    # ── STEP 7: Upload Short ─────────────────────────────────────────────────
    if start_step <= 7 and Path(short_path).exists():
        logger.info("[pipeline] Step 7: Uploading Short to YouTube...")
        from src.publish.youtube_10min import upload_video as upload_short
        upload_short(short_path, metadata_path=None, privacy="public")

    # ── STEP 8: Cleanup ──────────────────────────────────────────────────────
    cleanup_temp()
    purge_old_outputs(keep_last_n=3, active_date_str=date_str)

    # ── Log Success ──────────────────────────────────────────────────────────
    meta_data = json.loads(Path(metadata_path).read_text())
    log_posted(date_str, meta_data.get("title", "Unknown Topic"))

    notify("posts", f"🏁 Stoic Pipeline COMPLETE | date={date_str}")
    logger.info(f"[pipeline] COMPLETE | date={date_str}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modern Stoic Pipeline v11.0")
    parser.add_argument("--topic",    type=str, default=None,  help="Manual topic override")
    parser.add_argument("--date",     type=str, default=None,  help="YYYYMMDD override")
    parser.add_argument("--dry-run",  action="store_true",     help="Generate script only")
    parser.add_argument("--step",     type=int, default=1,     help="Resume from step N")
    parser.add_argument("--private",  action="store_true",     help="Upload as private")
    args = parser.parse_args()

    run(
        topic=args.topic,
        date_str=args.date,
        dry_run=args.dry_run,
        start_step=args.step,
        privacy="private" if args.private else "public",
    )