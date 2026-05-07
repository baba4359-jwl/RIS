@echo off
chcp 65001 >nul
title RIS 빌드

echo.
echo  ================================================
echo   RIS Windows 애플리케이션 빌드
echo  ================================================
echo.

REM ── 가상환경 확인 ────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [오류] .venv가 없습니다. start.bat을 먼저 실행하여 환경을 설정하세요.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

REM ── PyInstaller 설치 ─────────────────────────────────
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller 설치 중...
    pip install pyinstaller -q
)

REM ── 빌드 실행 ────────────────────────────────────────
echo 빌드 중... (처음 실행 시 5-10분 소요)
echo.
pyinstaller RIS.spec --noconfirm

if not exist "dist\RIS\RIS.exe" (
    echo.
    echo  ❌ 빌드 실패. 위 오류 메시지를 확인하세요.
    pause
    exit /b 1
)

REM ── .env 복사 ─────────────────────────────────────────
echo.
echo [배포 파일 준비 중...]
if exist ".env" (
    copy .env "dist\RIS\.env" >nul
    echo  .env 복사 완료
) else (
    echo  [주의] .env 파일이 없습니다. dist\RIS\.env 를 직접 생성하세요.
)

REM ── db 폴더 생성 ──────────────────────────────────────
if not exist "dist\RIS\db\" mkdir "dist\RIS\db"

echo.
echo  ✅ 빌드 완료!
echo.
echo  배포 방법:
echo   dist\RIS\ 폴더 전체를 zip으로 압축하여 전달하세요.
echo   사용자는 압축 해제 후 RIS.exe 를 더블클릭하면 됩니다.
echo.
pause
