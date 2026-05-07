@echo off
setlocal
title RIS Build

echo.
echo  ================================================
echo   RIS - Windows Application Build
echo  ================================================
echo.

REM Check virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] .venv not found. Run start.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

REM Install PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller -q
)

REM Remove entire dist\RIS to force clean bundle (stale packages cause runtime errors)
if exist "dist\RIS" rd /s /q "dist\RIS"

REM Build
echo Building... (first run may take 5-10 minutes^)
echo.
pyinstaller RIS.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller exited with an error. Check messages above.
    pause
    exit /b 1
)

if not exist "dist\RIS\RIS.exe" (
    echo.
    echo [ERROR] Build failed - RIS.exe not found.
    pause
    exit /b 1
)

REM Copy .env
echo.
echo Preparing distribution files...
if exist ".env" (
    copy .env "dist\RIS\.env" >nul
    echo  .env copied.
) else (
    echo  [WARNING] .env not found. Add dist\RIS\.env manually.
)

if not exist "dist\RIS\db\" mkdir "dist\RIS\db"

echo.
echo  Build complete!
echo.
echo  Distribute: zip the dist\RIS\ folder and send to users.
echo  Users double-click RIS.exe to launch.
echo.
pause
