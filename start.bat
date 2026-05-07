@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title PDF Research Intelligence

echo.
echo  ================================================
echo   PDF Research Intelligence
echo  ================================================
echo.

REM ── Python 확인 ────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo        https://www.python.org/downloads 에서 설치 후 다시 실행하세요.
    echo        설치 시 "Add Python to PATH" 옵션을 반드시 체크하세요.
    pause
    exit /b 1
)

REM ── 가상환경 생성 (최초 1회) ────────────────────────
if not exist ".venv\" (
    echo [1/3] 가상환경 생성 중...
    python -m venv .venv
    if errorlevel 1 (
        echo [오류] 가상환경 생성 실패
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

REM ── 패키지 설치 (최초 1회) ─────────────────────────
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [2/3] 패키지 설치 중 ^(최초 1회, 2-3분 소요^)...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [오류] 패키지 설치 실패
        pause
        exit /b 1
    )
) else (
    echo [2/3] 패키지 확인 완료
)

REM ── .env 설정 ───────────────────────────────────────
if not exist ".env" (
    echo [3/3] 초기 설정...
    copy .env.example .env >nul
    echo.
    echo  두 가지 API 키가 필요합니다 (모두 무료):
    echo   - Groq:    console.groq.com
    echo   - Voyage:  dash.voyageai.com
    echo.
    set /p GROQ_KEY=" Groq API Key 입력: "
    set /p VOYAGE_KEY=" Voyage API Key 입력: "
    powershell -Command "$c = Get-Content .env; $c = $c -replace 'GROQ_API_KEY=gsk_\.\.\.', ('GROQ_API_KEY=' + $env:GROQ_KEY); $c = $c -replace 'VOYAGE_API_KEY=pa-\.\.\.', ('VOYAGE_API_KEY=' + $env:VOYAGE_KEY); $c | Set-Content .env"
    echo.
    echo  설정 완료!
) else (
    echo [3/3] 환경 설정 확인 완료
)

REM ── 앱 실행 ─────────────────────────────────────────
echo.
echo  브라우저가 자동으로 열립니다...
echo  종료하려면 이 창을 닫으세요.
echo.
streamlit run app_main.py
