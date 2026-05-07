@echo off
setlocal enabledelayedexpansion
title PDF Research Intelligence

echo.
echo  ================================================
echo   PDF Research Intelligence - Setup and Launch
echo  ================================================
echo.

REM ── Python check ─────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Download and install from: https://www.python.org/downloads
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM ── Create virtual environment (first run only) ──────
if not exist ".venv\" (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

REM ── Install packages (first run only) ────────────────
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing packages (first run only, takes 2-3 min)...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Package installation failed.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Packages already installed.
)

REM ── Create .env (first run only) ─────────────────────
if not exist ".env" (
    echo [3/3] Initial setup...
    copy .env.example .env >nul
    echo.
    echo  Two free API keys are required:
    echo   - Groq:   https://console.groq.com
    echo   - Voyage: https://dash.voyageai.com
    echo.
    set /p GROQ_KEY="  Groq API Key: "
    set /p VOYAGE_KEY="  Voyage API Key: "
    powershell -Command "$c = Get-Content '.env'; $c = $c -replace 'GROQ_API_KEY=gsk_\.\.\.', ('GROQ_API_KEY=' + $env:GROQ_KEY); $c = $c -replace 'VOYAGE_API_KEY=pa-\.\.\.', ('VOYAGE_API_KEY=' + $env:VOYAGE_KEY); $c | Set-Content '.env'"
    echo.
    echo  Setup complete!
) else (
    echo [3/3] Configuration found.
)

REM ── Launch app ────────────────────────────────────────
echo.
echo  Starting app... Browser will open automatically.
echo  Close this window to stop the app.
echo.
streamlit run app_main.py
