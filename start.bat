@echo off
setlocal enabledelayedexpansion
title PDF Research Intelligence
cd /d "%~dp0"

echo.
echo  ================================================
echo   PDF Research Intelligence - Setup and Launch
echo  ================================================
echo.

REM ?? Step 1: Find Python 3.10-3.12 ???????????????????????????????????????????????
set "PYTHON_CMD="
set "PYTHON_VER="
call :detect_python

REM Auto-install if not found or too old
if defined PYTHON_CMD goto :python_ok

echo  [AUTO] Python 3.10+ not found. Attempting auto-install...
echo.

REM Method 1: winget
winget --version >nul 2>&1
if not errorlevel 1 (
    echo       Installing via winget...
    winget install Python.Python.3.11 --silent --scope user --accept-source-agreements --accept-package-agreements
    call :refresh_path
    call :detect_python
    if defined PYTHON_CMD echo       Python !PYTHON_VER! verified after winget install.
)

REM Method 2: Direct download
if defined PYTHON_CMD goto :python_ok
echo       Downloading Python 3.11 installer...
set "PYINST=%TEMP%\python_setup.exe"
powershell -NoProfile -Command "Invoke-WebRequest 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '!PYINST!' -UseBasicParsing" >nul 2>&1
if not exist "!PYINST!" goto :no_python
echo       Running installer (user-level, no admin required)...
"!PYINST!" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "!PYINST!" >nul 2>&1
call :refresh_path
call :detect_python
if defined PYTHON_CMD echo       Python !PYTHON_VER! verified after direct install.
if defined PYTHON_CMD goto :python_ok

:no_python
echo.
echo  [ERROR] Could not install Python automatically.
echo.
echo  Please install Python 3.11 64-bit manually:
echo    https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
echo.
echo  IMPORTANT:
echo    1. Download python-3.11.9-amd64.exe  (NOT 3.12 or 3.13)
echo    2. Check "Add Python to PATH" during installation
echo    3. Re-run this file after installation
echo.
echo  Note: Python 3.12+ is not supported -- chroma-hnswlib has no
echo        Windows wheel for 3.12+, causing installation to fail.
echo.
pause
exit /b 1

:python_ok
echo  [1/4] Python !PYTHON_VER! found.

REM Require 64-bit Python (chroma-hnswlib has no 32-bit pre-built wheel)
!PYTHON_CMD! -c "import struct; exit(0 if struct.calcsize('P')*8==64 else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] 32-bit Python detected. This app requires 64-bit Python.
    echo.
    echo  Please install Python 3.11 64-bit from:
    echo    https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo  Download: python-3.11.9-amd64.exe
    echo.
    pause
    exit /b 1
)

REM ?? Step 2: Virtual environment ??????????????????????????????????????????????
REM If existing venv is 32-bit, delete it so it gets recreated with 64-bit Python
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import struct; exit(0 if struct.calcsize('P')*8==64 else 1)" >nul 2>&1
    if errorlevel 1 (
        echo  [AUTO] Removing 32-bit virtual environment -- will recreate with 64-bit Python...
        rmdir /s /q .venv
    )
)

if not exist ".venv\" (
    echo  [2/4] Creating virtual environment...
    !PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo  [2/4] Virtual environment ready.
)

call .venv\Scripts\activate.bat

REM Upgrade pip inside venv before installing packages
python -m pip install --upgrade pip -q

REM ?? Step 3: Install packages ?????????????????????????????????????????????????
python -c "import streamlit, sentence_transformers, chromadb" >nul 2>&1
if errorlevel 1 (
    echo  [3/4] Installing packages -- first run takes 5-10 min, ~1.5 GB...
    pip install --prefer-binary -r requirements.txt
    if errorlevel 1 (
        echo  [ERROR] Package installation failed.
        pause
        exit /b 1
    )
) else (
    echo  [3/4] Packages ready.
)

REM ?? Step 4: Configure .env ???????????????????????????????????????????????????
if not exist ".env" (
    copy .env.example .env >nul
)
echo  [4/4] Configuration ready.

REM ?? Launch ???????????????????????????????????????????????????????????????????
echo.
echo  Starting app... Browser will open automatically.
echo  Close this window to stop the app.
echo.
streamlit run app_main.py
goto :eof


REM ?? Subroutines ??????????????????????????????????????????????????????????????

:check_ver
REM Exit /b 0 if 3.10 <= version <= 3.11, else exit /b 1
REM Upper bound 3.11: chroma-hnswlib==0.7.6 has no Windows wheel for Python 3.12+,
REM causing source compilation to fail on Windows without C++ Build Tools.
set "_CV=%~1"
set "_MAJ=0"
set "_MIN=0"
for /f "tokens=1,2 delims=." %%a in ("!_CV!") do (
    set /a "_MAJ=%%a" 2>nul
    set /a "_MIN=%%b" 2>nul
)
if !_MAJ! EQU 3 if !_MIN! GEQ 10 if !_MIN! LEQ 11 exit /b 0
exit /b 1

:refresh_path
REM Re-read PATH from registry after Python install.
set "_UPATH="
set "_SPATH="
for /f "skip=2 tokens=2,*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "_UPATH=%%b"
for /f "skip=2 tokens=2,*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "_SPATH=%%b"
if defined _UPATH set "PATH=!PATH!;!_UPATH!"
if defined _SPATH set "PATH=!PATH!;!_SPATH!"
exit /b 0

:detect_python
REM Try 'python' then 'py -3' and set PYTHON_CMD / PYTHON_VER if version is valid.
set "_TMP="
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "_TMP=%%v"
if defined _TMP (
    call :check_ver "!_TMP!"
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
        set "PYTHON_VER=!_TMP!"
        exit /b 0
    )
)
set "_TMP="
for /f "tokens=2" %%v in ('py -3 --version 2^>^&1') do set "_TMP=%%v"
if defined _TMP (
    call :check_ver "!_TMP!"
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        set "PYTHON_VER=!_TMP!"
        exit /b 0
    )
)
exit /b 1