"""
YouTube publisher for 10-minute Stoic videos.
No GDrive relay. Direct upload.
"""

import json
import logging
import os
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from src.auth import get_google_credentials
from src.utils.discord import notify
from src.utils.logger import get_logger

logger = get_logger("publish.youtube_10min")

CHUNK_SIZE   = 10 * 1024 * 1024  # 10 MB chunks
REQUIRED_TAGS = [
    "stoicism", "marcus aurelius", "seneca", "mental toughness", 
    "discipline", "personal growth", "psychology", "modern stoic", 
    "overthinking", "mindset"
]


def _get_youtube():
    return build("youtube", "v3", credentials=get_google_credentials(), cache_discovery=False)


def _validate_title(title: str) -> str:
    """Ensure title is within limits."""
    return title[:100]


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def upload_video(
    video_path: str,
    metadata_path: str | None = None,
    privacy: str = "public",
) -> str:
    """
    Upload the video directly to YouTube.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    meta = {}
    if metadata_path and Path(metadata_path).exists():
        meta = json.loads(Path(metadata_path).read_text(encoding="utf-8"))

    title = _validate_title(meta.get("title", f"Stoic Lesson - {Path(video_path).stem}"))
    desc  = meta.get("description", "Daily Stoic wisdom for modern life.")
    tags  = meta.get("tags", [])

    # Ensure all required tags are present
    tags_lower = [t.lower() for t in tags]
    for req in REQUIRED_TAGS:
        if req not in tags_lower:
            tags.append(req)

    logger.info(f"[youtube] Uploading: '{title}' | privacy={privacy}")
    notify("logs", f"📤 Uploading to YouTube | **{title}** | privacy: {privacy}")

    yt   = _get_youtube()
    body = {
        "snippet": {
            "title": title,
            "description": desc,
            "tags": tags,
            "categoryId": "27", # Education
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=CHUNK_SIZE)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct % 20 == 0:
                    logger.info(f"[youtube] Upload progress: {pct}%")
        except Exception as e:
            logger.warning(f"[youtube] Chunk error: {e} — retrying...")
            time.sleep(5)

    video_id  = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Post pinned comment
    pinned = meta.get("pinned_comment", "Which of these Stoic rules hit hardest for you today?")
    try:
        yt.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": pinned}
                    }
                }
            }
        ).execute()
    except Exception as e:
        logger.warning(f"[youtube] Pinned comment failed (non-fatal): {e}")

    logger.info(f"[youtube] DONE | id={video_id}")
    notify("posts", f"🎥 Video live!\n**{title}**\n🔗 {video_url}")

    return video_id
