"""
Discord webhook notification utility for Xity Sleep Bible.

Purpose:
    Deliver structured pipeline status messages to 5 Discord channels.
    All messages include timestamp and calling function name automatically.
    Pings @Kyrell by Discord user ID on #factory-errors only.

Channel map (configured via .env):
    DISCORD_WEBHOOK_QUEUE    → #factory-queue    (script generated, TTS starting)
    DISCORD_WEBHOOK_LOGS     → #factory-logs     (step-by-step status)
    DISCORD_WEBHOOK_ERRORS   → #factory-errors   (exceptions, API failures, retries)
    DISCORD_WEBHOOK_POSTS    → #factory-posts     (final YouTube URL + schedule)
    DISCORD_WEBHOOK_INSIGHTS → #factory-insights  (weekly analytics)

Error conditions:
    Network failure on send → retried via tenacity (5 attempts, exponential backoff).
    If all retries fail, error is printed to stderr only — never crashes the pipeline.
"""

import inspect
import os
import traceback
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

load_dotenv()

# ── Webhook URL map ────────────────────────────────────────────────────────────
_CHANNEL_MAP: dict[str, str | None] = {
    "queue":    os.getenv("DISCORD_WEBHOOK_QUEUE"),
    "logs":     os.getenv("DISCORD_WEBHOOK_LOGS"),
    "errors":   os.getenv("DISCORD_WEBHOOK_ERRORS"),
    "posts":    os.getenv("DISCORD_WEBHOOK_POSTS"),
    "insights": os.getenv("DISCORD_WEBHOOK_INSIGHTS"),
}

_KYRELL_ID: str = os.getenv("DISCORD_KYRELL_USER_ID", "")


# ── Internal retry-wrapped POST ────────────────────────────────────────────────
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _post_webhook(url: str, payload: dict) -> None:
    """
    POST a JSON payload to a Discord webhook with retry.

    Args:
        url (str): Discord webhook URL.
        payload (dict): JSON body (Discord message format).

    Error conditions:
        HTTP error status → raises requests.HTTPError → retried by tenacity.
    """
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


# ── Public notify function ─────────────────────────────────────────────────────
def notify(
    channel: str,
    message: str,
    ping_kyrell: bool = False,
    error_info: Exception | None = None,
    retry_attempt: int | None = None,
) -> None:
    """
    Send a structured message to a Discord webhook channel.

    Purpose:
        Central notification hub for all pipeline events. Automatically
        includes UTC timestamp and the calling function name. Formats error
        tracebacks as code blocks. Pings @Kyrell exclusively on the
        #factory-errors channel.

    Args:
        channel (str): One of: 'queue', 'logs', 'errors', 'posts', 'insights'.
        message (str): Human-readable message body.
        ping_kyrell (bool): Force @Kyrell mention. Also auto-forced on 'errors'.
        error_info (Exception | None): If provided, appends truncated traceback.
        retry_attempt (int | None): If provided, appends retry count annotation.

    Returns:
        None

    Error conditions:
        Missing webhook URL → prints warning, returns silently (no crash).
        Network failure after 5 retries → prints to stderr, returns silently.
    """
    webhook_url = _CHANNEL_MAP.get(channel)
    if not webhook_url:
        print(f"[Discord] WARNING: No webhook configured for channel '{channel}'")
        return

    # Resolve the calling function name for context
    try:
        caller = inspect.stack()[1].function
    except Exception:
        caller = "unknown"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Build message body ────────────────────────────────────────────────────
    parts = [f"**[{ts}]** `{caller}` — {message}"]

    if retry_attempt is not None:
        parts.append(f"⟳ Retry **{retry_attempt}/5**")

    if error_info is not None:
        tb = "".join(
            traceback.format_exception(type(error_info), error_info, error_info.__traceback__)
        )
        # Discord message limit is 2000 chars — cap traceback at 1400 to leave room
        parts.append(f"```\n{tb[-1400:]}\n```")

    body = "\n".join(parts)

    # ── Kyrell ping (errors only or explicit) ────────────────────────────────
    if channel == "errors" or ping_kyrell:
        mention = f"<@{_KYRELL_ID}> " if _KYRELL_ID else "@Kyrell "
        body = mention + body

    # Discord enforces a 2000-character message limit
    if len(body) > 1990:
        body = body[:1987] + "…"

    payload = {"content": body}

    # ── Send with retry ───────────────────────────────────────────────────────
    try:
        _post_webhook(webhook_url, payload)
    except RetryError as exc:
        print(f"[Discord] FAILED after 5 retries on channel '{channel}': {exc}")
    except Exception as exc:
        print(f"[Discord] Unexpected error on channel '{channel}': {exc}")
