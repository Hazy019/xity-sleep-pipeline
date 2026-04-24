"""
GDrive Asset Manager — v3.0 (Read-Only)
========================================
Downloads background videos and music FROM Google Drive.
NEVER uploads anything to Drive.
The pipeline uses Drive purely as a remote asset library.

Drive folder IDs (confirmed live):
  BG Video:  1XEFf6Qb1GzMRuaR9JTsXZLww9G9tkC7S
  BG Music:  12ALHDvSSKKRjrzrdH4Iix2Z9OVnTupM7
"""

import hashlib
import io
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from src.auth import get_google_credentials
from src.utils.logger import get_logger
from src.utils.discord import notify

logger = get_logger("cloud.gdrive_assets")

ASSETS_DIR = Path("assets")
BG_VIDEO_DIR = ASSETS_DIR / "backgrounds"
BG_MUSIC_DIR = ASSETS_DIR / "music"

BG_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
BG_MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# Confirmed Drive folder IDs
DRIVE_BG_VIDEO_FOLDER = "1XEFf6Qb1GzMRuaR9JTsXZLww9G9tkC7S"
DRIVE_BG_MUSIC_FOLDER = "12ALHDvSSKKRjrzrdH4Iix2Z9OVnTupM7"


def _get_drive_service():
    creds = get_google_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list_folder(service, folder_id: str) -> list[dict]:
    """List all files in a Drive folder."""
    result = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, size)",
        pageSize=50
    ).execute()
    return result.get("files", [])


def _download_file(service, file_id: str, dest_path: Path) -> None:
    """Download a Drive file to a local path."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request, chunksize=10 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest_path.write_bytes(fh.getvalue())
    logger.info(f"[gdrive_assets] Downloaded: {dest_path.name} ({dest_path.stat().st_size / 1024 / 1024:.1f} MB)")


def sync_assets(force: bool = False) -> dict:
    """
    Ensure all BG videos and music are downloaded locally.
    """
    service = _get_drive_service()
    result = {"backgrounds": {}, "music": {}}

    for folder_id, local_dir, key in [
        (DRIVE_BG_VIDEO_FOLDER, BG_VIDEO_DIR, "backgrounds"),
        (DRIVE_BG_MUSIC_FOLDER, BG_MUSIC_DIR, "music"),
    ]:
        try:
            files = _list_folder(service, folder_id)
            for f in files:
                name = f["name"]
                dest = local_dir / name
                if not dest.exists() or force:
                    logger.info(f"[gdrive_assets] Fetching from Drive: {name}")
                    notify("logs", f"⬇️ Downloading asset: `{name}`")
                    _download_file(service, f["id"], dest)
                else:
                    logger.debug(f"[gdrive_assets] Cached locally: {name}")
                result[key][name] = str(dest)
        except Exception as e:
            logger.error(f"[gdrive_assets] Error syncing folder {folder_id}: {e}")

    logger.info(f"[gdrive_assets] Sync complete. BG videos: {len(result['backgrounds'])}, Music: {len(result['music'])}")
    return result


def get_background_path(filename: str) -> str:
    """Returns local path for a BG video, downloading if needed."""
    dest = BG_VIDEO_DIR / filename
    if not dest.exists():
        service = _get_drive_service()
        files = _list_folder(service, DRIVE_BG_VIDEO_FOLDER)
        
        # Exact match
        for f in files:
            if f["name"] == filename:
                _download_file(service, f["id"], dest)
                return str(dest)
        
        # Fuzzy match (stem match or contains stem)
        target_stem = Path(filename).stem.split(" (")[0].lower() # handle "name (1).mp4"
        for f in files:
            f_name = f["name"].lower()
            if target_stem in f_name:
                logger.info(f"[gdrive_assets] Fuzzy match found: {f['name']} for {filename}")
                dest_fuzzy = BG_VIDEO_DIR / f["name"]
                if not dest_fuzzy.exists():
                    _download_file(service, f["id"], dest_fuzzy)
                return str(dest_fuzzy)
                
        raise FileNotFoundError(f"Background '{filename}' not found in Drive folder.")
    return str(dest)


def get_music_path(filename: str) -> str:
    """Returns local path for a BG music file, downloading if needed."""
    dest = BG_MUSIC_DIR / filename
    if not dest.exists():
        service = _get_drive_service()
        files = _list_folder(service, DRIVE_BG_MUSIC_FOLDER)
        
        for f in files:
            if f["name"] == filename:
                _download_file(service, f["id"], dest)
                return str(dest)
                
        # Fuzzy match
        target_stem = Path(filename).stem.split("-")[0].lower()
        for f in files:
            if target_stem in f["name"].lower():
                dest_fuzzy = BG_MUSIC_DIR / f["name"]
                if not dest_fuzzy.exists():
                    _download_file(service, f["id"], dest_fuzzy)
                return str(dest_fuzzy)
                
        raise FileNotFoundError(f"Music '{filename}' not found in Drive folder.")
    return str(dest)
