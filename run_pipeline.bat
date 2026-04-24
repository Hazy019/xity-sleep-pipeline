@echo off
:: ============================================================
:: Xity Sleep Bible — Pipeline Launcher for Windows Task Scheduler
:: ============================================================
:: This batch file activates the virtual environment and runs
:: the pipeline. It is the entry point called by Task Scheduler.
::
:: Usage (manual): run_pipeline.bat
:: Usage (Task Scheduler): point the task action to this file.
::
:: To pass arguments: run_pipeline.bat --dry-run
::                    run_pipeline.bat --step 4 --date 20260418

setlocal

:: ── Set the project root (adjust if you move the project) ──
set PROJECT_DIR=%~dp0

:: ── Activate virtual environment ───────────────────────────
call "%PROJECT_DIR%.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Could not activate venv at %PROJECT_DIR%.venv
    echo Run: python -m venv .venv ^&^& pip install -r requirements.txt
    exit /b 1
)

:: ── Run the pipeline ────────────────────────────────────────
echo [%date% %time%] Launching Xity Sleep Bible pipeline...
python "%PROJECT_DIR%pipeline.py" %*

:: ── Log exit code ───────────────────────────────────────────
if errorlevel 1 (
    echo [%date% %time%] Pipeline FAILED with exit code %errorlevel%
    exit /b %errorlevel%
) else (
    echo [%date% %time%] Pipeline completed successfully.
)

endlocal
