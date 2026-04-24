"""
YouTube Analytics reporter for Xity Sleep Bible.

Purpose:
    Pull last 7 days of YouTube Analytics (views, watch time, US audience %).
    Post structured report to #factory-insights Discord channel.
    Save raw JSON to outputs/analytics/.

    Designed to run as a standalone weekly cron job — Saturday 9 AM EST.
    Can also be called inline from the pipeline if needed.

Milestone tracking:
    US audience share target: ≥50%
    Reports gap between current US% and target on every run.

Error conditions:
    - YouTube Analytics API not enabled → HttpError 403 with setup link
    - YOUTUBE_CHANNEL_ID missing → EnvironmentError
    - API quota exceeded → retried via tenacity (5×)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from src.utils.discord import notify
from src.utils.logger import get_logger

load_dotenv()

logger = get_logger("analytics.reporter")

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]
CREDENTIALS_FILE  = Path("config/credentials.json")
TOKEN_FILE        = Path("config/token_analytics.json")
ANALYTICS_DIR     = Path("outputs/analytics")
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

US_SHARE_TARGET = 50.0    # milestone: ≥50% US audience


# ── Auth ───────────────────────────────────────────────────────────────────────
def _get_analytics_service():
    """
    Return an authenticated YouTube Analytics API v2 service object.

    Error conditions:
        credentials.json missing → FileNotFoundError with setup instructions.
    """
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Google credentials not found: {CREDENTIALS_FILE}\n"
                    "Enable 'YouTube Analytics API' in your GCP project first:\n"
                    "  https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)


# ── Main analytics pull ────────────────────────────────────────────────────────
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def weekly_analytics_pull() -> dict:
    """
    Pull last 7 days of YouTube Analytics and post to #factory-insights.

    Purpose:
        Queries overall views and watch time, then a country-breakdown query
        to compute the US audience percentage. Reports against the 50% US
        milestone target and saves raw data as JSON.

    Returns:
        dict: {
            date_range (str), views (int), watch_hours (float),
            us_pct (float), us_views (int), milestone_gap (float),
            top_countries (list), raw_json_path (str)
        }

    Error conditions:
        - YOUTUBE_CHANNEL_ID not in .env → EnvironmentError
        - Analytics API not enabled → HttpError 403 with activation link
        - Network failure → retried up to 5× via tenacity
    """
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
    if not channel_id:
        raise EnvironmentError(
            "YOUTUBE_CHANNEL_ID not set in .env\n"
            "Find it: YouTube Studio → Settings → Channel → Advanced settings"
        )

    today      = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=7)).isoformat()
    end_date   = today.isoformat()

    logger.info(f"[weekly_analytics_pull] START | range={start_date} → {end_date}")
    notify("insights", f"📊 Pulling weekly analytics | `{start_date}` → `{end_date}`")

    try:
        svc = _get_analytics_service()

        # ── Overall metrics ────────────────────────────────────────────────────
        overall = svc.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched",
        ).execute()

        rows              = overall.get("rows") or [[0, 0]]
        total_views       = int(float(rows[0][0]))
        total_watch_mins  = float(rows[0][1])
        total_watch_hours = total_watch_mins / 60

        # ── Country breakdown ──────────────────────────────────────────────────
        geo = svc.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="country",
            sort="-views",
            maxResults=15,
        ).execute()

        geo_rows      = geo.get("rows") or []
        total_geo     = sum(int(float(r[1])) for r in geo_rows) or 1
        us_views      = next((int(float(r[1])) for r in geo_rows if r[0] == "US"), 0)
        us_pct        = round((us_views / total_geo) * 100, 1)
        milestone_gap = max(0.0, US_SHARE_TARGET - us_pct)

    except HttpError as exc:
        if exc.resp.status == 403:
            msg = (
                "🚨 YouTube Analytics API → 403 Forbidden.\n"
                "Enable it here: https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com"
            )
            notify("errors", msg, ping_kyrell=True)
        raise

    # ── Build summary ──────────────────────────────────────────────────────────
    summary = {
        "date_range":    f"{start_date} → {end_date}",
        "views":         total_views,
        "watch_hours":   round(total_watch_hours, 1),
        "us_pct":        us_pct,
        "us_views":      us_views,
        "milestone_gap": round(milestone_gap, 1),
        "top_countries": geo_rows[:5],
    }

    date_str  = datetime.now().strftime("%Y%m%d")
    json_path = ANALYTICS_DIR / f"analytics_{date_str}.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ── Discord report ─────────────────────────────────────────────────────────
    if milestone_gap == 0:
        milestone_line = f"🏆 **US milestone reached!** ({us_pct}% ≥ {US_SHARE_TARGET}%)"
    else:
        milestone_line = f"📍 US milestone gap: **{milestone_gap:.1f}%** remaining (currently {us_pct}%)"

    report = (
        f"**📊 Weekly Analytics | {start_date} → {end_date}**\n"
        f"👁️ Views: **{total_views:,}**\n"
        f"⏱️ Watch hours: **{total_watch_hours:,.1f} hrs**\n"
        f"🇺🇸 US audience: **{us_pct}%** ({us_views:,} views)\n"
        f"{milestone_line}\n"
        f"📁 Raw data: `analytics_{date_str}.json`"
    )
    notify("insights", report)

    summary["raw_json_path"] = str(json_path)
    logger.info(
        f"[weekly_analytics_pull] END | views={total_views:,} | "
        f"us_pct={us_pct}% | watch_hours={total_watch_hours:.1f}"
    )

    return summary
