"""
Storage management utilities for Xity Sleep Bible.

Purpose:
    Prevents local disk exhaustion by purging old video, audio, and script files
    while ensuring temporary directories are kept clean.
"""

import os
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger("utils.cleanup")

OUTPUTS_DIR = Path("outputs")
VIDEO_DIR   = OUTPUTS_DIR / "video"
AUDIO_DIR   = OUTPUTS_DIR / "audio"
SCRIPT_DIR  = OUTPUTS_DIR / "scripts"
TEMP_DIR    = OUTPUTS_DIR / "temp"

def purge_old_outputs(keep_last_n: int = 2, active_date_str: str | None = None) -> None:
    """
    Remove old output files from video, audio, and scripts directories, 
    keeping only the most recent 'n' files.

    Args:
        keep_last_n (int): Number of most recent files to preserve per directory.
        active_date_str (str): YYYYMMDD string of the current target date to protect.
    """
    targets = [VIDEO_DIR, AUDIO_DIR, SCRIPT_DIR]
    
    for folder in targets:
        if not folder.exists():
            continue
            
        # Get all files, sorted by modification time (oldest first)
        files = sorted(
            [f for f in folder.iterdir() if f.is_file()],
            key=os.path.getmtime
        )
        
        if len(files) <= keep_last_n:
            continue
            
        from datetime import datetime
        today_prefix = datetime.now().strftime("%Y%m%d")
        
        to_delete = []
        # Filter out files that belong to today OR the active target date,
        # and keep the most recent N files.
        preserved = 0
        for f in reversed(files):
            # Protect files if they match today's date OR the active production date
            is_active = (today_prefix in f.name) or (active_date_str and active_date_str in f.name)
            
            if is_active or preserved < keep_last_n:
                preserved += 1
                continue
                
            to_delete.append(f)
        
        for f in to_delete:
            try:
                size_mb = f.stat().st_size / (1024 * 1024)
                f.unlink()
                logger.info(f"[purge_old_outputs] Deleted old file: {f.name} ({size_mb:.1f} MB)")
            except Exception as e:
                logger.warning(f"[purge_old_outputs] Failed to delete {f.name}: {e}")

def cleanup_temp() -> None:
    """
    Clear all files in the outputs/temp directory.
    """
    if not TEMP_DIR.exists():
        return
        
    for f in TEMP_DIR.iterdir():
        if f.is_file():
            try:
                f.unlink()
                logger.debug(f"[cleanup_temp] Deleted temp file: {f.name}")
            except Exception as e:
                logger.warning(f"[cleanup_temp] Failed to delete temp file {f.name}: {e}")
    
    logger.info("[cleanup_temp] Temporary directory cleared.")
