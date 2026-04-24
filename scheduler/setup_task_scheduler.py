"""
Windows Task Scheduler setup for Xity Sleep Bible Pipeline.

Registers two scheduled tasks:
    1. XitySleepPipeline  — Runs pipeline.py on Tuesday and Friday at 6:00 PM EST
                            (2 hours before the 8 PM publish slot — enough lead time
                            for script generation, TTS, encoding, and uploading)
    2. XitySleepAnalytics — Runs pipeline.py --analytics-only every Saturday at
                            9:00 AM EST

Usage:
    python scheduler/setup_task_scheduler.py

Requires:
    - Run as Administrator (Task Scheduler requires elevated privileges)
    - Python venv activated OR full path to python.exe specified in VENV_PYTHON below
    - Project root directory correct in PROJECT_DIR below
"""

import os
import subprocess
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_DIR  = Path(__file__).resolve().parent.parent
VENV_PYTHON  = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
PIPELINE_PY  = PROJECT_DIR / "pipeline.py"

# EST is UTC-5 (UTC-4 in summer/EDT). Task Scheduler uses local time.
# Set your system timezone to Eastern Time, or adjust these hours accordingly.
# 6:00 PM local (Eastern) = pipeline runs, publishes 2 hours later at 8 PM.
PIPELINE_HOUR   = "18:00"   # 6:00 PM local time (EST = UTC-5)
ANALYTICS_HOUR  = "09:00"   # 9:00 AM local time Saturday


def _run_schtasks(args: list[str]) -> None:
    """Run a schtasks.exe command and print the result."""
    cmd = ["schtasks"] + args
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}")
        sys.exit(1)
    print(f"OK: {result.stdout.strip()}")


def register_pipeline_task() -> None:
    """
    Register the XitySleepPipeline task — runs Tuesday and Friday at 6 PM.

    Purpose:
        Creates a weekly recurring task that runs on both Tuesday and Friday.
        Windows Task Scheduler's /sc weekly /d flag accepts comma-separated days.

    Error conditions:
        schtasks failure → prints error and exits.
    """
    python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    task_cmd   = f'"{python_exe}" "{PIPELINE_PY}"'

    print("\n[1/2] Registering XitySleepPipeline task (Tue + Fri at 6 PM)...")

    # Delete existing task if present (idempotent)
    subprocess.run(
        ["schtasks", "/delete", "/tn", "XitySleepPipeline", "/f"],
        capture_output=True,
    )

    _run_schtasks([
        "/create",
        "/tn",  "XitySleepPipeline",
        "/tr",  task_cmd,
        "/sc",  "weekly",
        "/d",   "TUE,FRI",
        "/st",  PIPELINE_HOUR,
        "/sd",  "01/01/2026",
        "/rl",  "HIGHEST",        # run with highest available privileges
        "/ru",  "SYSTEM",         # or replace with your Windows username
        "/f",                     # force create (overwrite if exists)
    ])


def register_analytics_task() -> None:
    """
    Register the XitySleepAnalytics task — runs every Saturday at 9 AM.

    Purpose:
        Weekly analytics pull separate from the main pipeline so it can
        report independently even if no video was published that week.

    Error conditions:
        schtasks failure → prints error and exits.
    """
    python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    task_cmd   = f'"{python_exe}" "{PIPELINE_PY}" --analytics-only'

    print("\n[2/2] Registering XitySleepAnalytics task (Saturday at 9 AM)...")

    subprocess.run(
        ["schtasks", "/delete", "/tn", "XitySleepAnalytics", "/f"],
        capture_output=True,
    )

    _run_schtasks([
        "/create",
        "/tn",  "XitySleepAnalytics",
        "/tr",  task_cmd,
        "/sc",  "weekly",
        "/d",   "SAT",
        "/st",  ANALYTICS_HOUR,
        "/sd",  "01/01/2026",
        "/rl",  "HIGHEST",
        "/ru",  "SYSTEM",
        "/f",
    ])


def verify_tasks() -> None:
    """Print registered task status for both tasks."""
    print("\n── Registered Tasks ──────────────────────────────────────────────")
    for name in ("XitySleepPipeline", "XitySleepAnalytics"):
        result = subprocess.run(
            ["schtasks", "/query", "/tn", name, "/fo", "LIST"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"  Task '{name}': NOT FOUND")
    print("──────────────────────────────────────────────────────────────────")


def main() -> None:
    if os.name != "nt":
        print("ERROR: This script is for Windows Task Scheduler only.")
        sys.exit(1)

    print("╔═══════════════════════════════════════════════╗")
    print("║  Xity Sleep Bible — Task Scheduler Setup      ║")
    print("╚═══════════════════════════════════════════════╝")
    print(f"Project dir : {PROJECT_DIR}")
    print(f"Python exec : {VENV_PYTHON if VENV_PYTHON.exists() else sys.executable}")
    print(f"Pipeline    : {PIPELINE_PY}")

    if not PIPELINE_PY.exists():
        print(f"\nERROR: pipeline.py not found at {PIPELINE_PY}")
        sys.exit(1)

    register_pipeline_task()
    register_analytics_task()
    verify_tasks()

    print("\n✅ Task Scheduler setup complete.")
    print("   Pipeline:  Tuesday & Friday at 6:00 PM (local/Eastern)")
    print("   Analytics: Saturday at 9:00 AM (local/Eastern)")
    print("\nNOTE: Ensure your system timezone is set to Eastern Time,")
    print("      or adjust PIPELINE_HOUR/ANALYTICS_HOUR in this script.")


if __name__ == "__main__":
    main()
