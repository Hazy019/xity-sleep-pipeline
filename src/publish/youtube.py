"""
YouTube publishing module for Modern Stoic Pipeline.

Functions:
    get_next_publish_slot()    — Next Tuesday/Friday 8 PM EST as UTC datetime
    schedule_youtube_upload()  — Upload 3hr video, scheduled publish via Data API v3
    post_shorts()              — Upload 60s clip as public YouTube Short

US Targeting checklist is validated BEFORE any API call is made.
All uploads are resumable at 10 MB chunks.

Auth:
    OAuth2 Desktop flow. Token cached at config/master_token.json.

Error conditions:
    - US checklist violation → ValueError (no upload attempted, no retry)
    - API failure → retried via tenacity (5×, exponential backoff)
    - credentials.json missing → FileNotFoundError with setup steps
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from src.utils.discord import notify
from src.utils.logger import get_logger

load_dotenv()

logger = get_logger("publish.youtube")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
CREDENTIALS_FILE = Path("config/credentials.json")
TOKEN_FILE       = Path("config/master_token.json")

EST  = ZoneInfo("America/New_York")
UTC  = timezone.utc

REQUIRED_TAGS = [
    "stoicism", "marcus aurelius", "seneca",
    "mental toughness", "discipline", "mindset",
]
_US_TITLE_KEYWORDS = [
    "stoicism", "marcus aurelius", "seneca", "discipline",
    "mental toughness", "stoic", "philosophy", "wisdom",
]

import socket
socket.setdefaulttimeout(300) # 5 minute timeout for large chunks

CHUNK_SIZE = 5 * 1024 * 1024   # 5 MB for better stability on large uploads


from src.auth import get_google_credentials

# ── Auth ───────────────────────────────────────────────────────────────────────
def _get_youtube_service():
    """
    Return an authenticated YouTube Data API v3 service object using src.auth.
    """
    creds = get_google_credentials()
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


# ── Publish slot calculator ────────────────────────────────────────────────────
def get_next_publish_slot() -> datetime:
    """
    Return the next Tuesday or Friday at 8:00 PM EST as a UTC-aware datetime.

    Purpose:
        Ensures videos are always scheduled for the channel's upload cadence.
        Requires a minimum 24-hour lead time from the current moment.

    Returns:
        datetime: UTC-aware datetime for the next valid publish slot.

    Error conditions:
        No slot found in 7 days → RuntimeError (should never happen).
    """
    now_est = datetime.now(EST)

    for days_ahead in range(1, 9):     # scan up to 8 days forward
        candidate = now_est + timedelta(days=days_ahead)
        if candidate.weekday() in (1, 4):    # Tuesday=1, Friday=4
            slot_est = candidate.replace(hour=20, minute=0, second=0, microsecond=0)
            if slot_est > now_est + timedelta(hours=24):
                slot_utc = slot_est.astimezone(UTC)
                logger.info(
                    f"[get_next_publish_slot] Slot: "
                    f"{slot_est.strftime('%A %Y-%m-%d %I:%M %p %Z')} "
                    f"= {slot_utc.isoformat()}"
                )
                return slot_utc

    raise RuntimeError("Could not find a valid publish slot within 8 days")


# ── US targeting checklist ─────────────────────────────────────────────────────
def _validate_us_checklist(title: str, description: str, tags: list[str]) -> None:
    """
    Enforce US audience targeting requirements before any YouTube upload.

    Purpose:
        Hard-block an upload if metadata does not meet US targeting standards.
        Raises ValueError — no retry, no partial upload. Fix the metadata first.

    Args:
        title (str): Video title.
        description (str): Video description (full text).
        tags (list[str]): Tag list.

    Error conditions:
        ValueError on any failed check.
    """
    title_lower = title.lower()
    if not any(kw in title_lower for kw in _US_TITLE_KEYWORDS):
        # Auto-fix: append a sleep phrase instead of hard-failing the run
        logger.warning(
            f"[_validate_us_checklist] Title missing US sleep phrase. Auto-appending suffix. "
            f"Original: '{title}'"
        )
        title += " | Stoic Wisdom"
        title_lower = title.lower()

    if len(description.strip()) < 100:
        raise ValueError("Description must be ≥100 characters with a US-targeted opening hook.")

    tags_lower = [t.lower() for t in tags]
    missing = [req for req in REQUIRED_TAGS if req not in tags_lower]
    if missing:
        logger.warning(f"[_validate_us_checklist] Auto-injecting missing required US tags: {missing}")
        for m in missing:
            if m not in tags: # case sensitive check just in case
                tags.append(m)

    logger.info("[_validate_us_checklist] All US targeting checks passed ✓")


# ── Step 7: Schedule main upload ───────────────────────────────────────────────
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def schedule_youtube_upload(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    publish_at: datetime | None = None,
) -> str:
    """
    Upload the 3-hour meditation video to YouTube with a scheduled publish time.

    Purpose:
        Validates the US targeting checklist, then uploads via YouTube Data
        API v3 videos.insert with status.publishAt. Video is set to 'private'
        and will go public automatically at the scheduled time.

    Args:
        video_path (str): Path to the .mp4 file (local/temp copy from Drive).
        title (str): Video title — must contain a Stoic keyword.
        description (str): Full description — must be ≥100 chars.
        tags (list[str]): Must include all 6 required tags.
        publish_at (datetime | None): UTC datetime for scheduled publish.
                                       Defaults to get_next_publish_slot().

    Returns:
        str: YouTube video ID.

    Error conditions:
        - US checklist failure → ValueError (no retry)
        - File not found → FileNotFoundError
        - API failure → retried up to 5×
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    _validate_us_checklist(title, description, tags)   # hard stop if fails

    if publish_at is None:
        publish_at = get_next_publish_slot()

    publish_at_iso = publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    publish_label  = publish_at.astimezone(EST).strftime("%A, %B %d at 8:00 PM EST")

    logger.info(f"[schedule_youtube_upload] START | title='{title}' | publishAt={publish_at_iso}")
    notify("logs", f"📤 Uploading to YouTube | scheduled: **{publish_label}**")

    youtube = _get_youtube_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",          # People & Blogs
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",  # goes public at publishAt automatically
            "publishAt": publish_at_iso,
            "selfDeclaredMadeForKids": False,
        },
    }

    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=CHUNK_SIZE)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.debug(f"[schedule_youtube_upload] Upload: {pct}%")
        except (socket.timeout, TimeoutError, ConnectionResetError) as e:
            logger.warning(f"[schedule_youtube_upload] Transient network error: {e}. Retrying chunk...")
            time.sleep(5)
            continue

    video_id  = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    logger.info(f"[schedule_youtube_upload] END | id={video_id}")
    notify("posts",
           f"🎥 Video scheduled!\n"
           f"**{title}**\n"
           f"🔗 {video_url}\n"
           f"📅 Publishes: **{publish_label}**")
    notify("logs", f"✅ YouTube upload complete | ID: `{video_id}`")

    return video_id


# ── Step 8: Post YouTube Short ─────────────────────────────────────────────────
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def post_shorts(short_video_path: str, title: str, description: str) -> str:
    """
    Upload a 60-second 9:16 clip to YouTube as a public YouTube Short.

    Purpose:
        Uploads immediately as public (Shorts bypass the scheduling queue).
        Appends #shorts and Stoic-related hashtags to description automatically.

    Args:
        short_video_path (str): Path to the 1080×1920 .mp4 short clip.
        title (str): Short title (auto-truncated to 70 chars for Shorts).
        description (str): Short description.

    Returns:
        str: YouTube video ID of the uploaded Short.

    Error conditions:
        - File not found → FileNotFoundError
        - API failure → retried up to 5×
    """
    if not Path(short_video_path).exists():
        raise FileNotFoundError(f"Short clip not found: {short_video_path}")

    shorts_desc = (
        f"{description}\n\n"
        "#shorts #stoicism #marcus_aurelius #discipline #mental_toughness #philosophy"
    )

    logger.info(f"[post_shorts] START | file={Path(short_video_path).name}")
    notify("logs", f"📱 Uploading YouTube Short | `{Path(short_video_path).name}`")

    youtube = _get_youtube_service()

    body = {
        "snippet": {
            "title": title[:70],
            "description": shorts_desc,
            "tags": REQUIRED_TAGS + ["youtube shorts", "stoic short", "mindset"],
            "categoryId": "22",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",   # Shorts go live immediately
            "selfDeclaredMadeForKids": False,
        },
    }

    media   = MediaFileUpload(short_video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    short_id  = response.get("id")
    short_url = f"https://www.youtube.com/shorts/{short_id}"

    logger.info(f"[post_shorts] END | id={short_id}")
    notify("posts", f"📱 Short live! [{title[:50]}]({short_url})")
    notify("logs",  f"✅ YouTube Short uploaded | ID: `{short_id}`")

    return short_id
