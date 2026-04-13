@echo off
echo ============================================
echo  Frame Extraction Service - Startup Script
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

REM Check ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] ffmpeg not found in PATH.
    echo           Download from: https://ffmpeg.org/download.html
    echo           Or install via: winget install ffmpeg
    echo.
    echo           If ffmpeg is installed elsewhere, set:
    echo             set FFMPEG_BIN=C:\path\to\ffmpeg.exe
    echo             set FFPROBE_BIN=C:\path\to\ffprobe.exe
    echo.
)

REM Install Flask if not present
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Flask...
    pip install flask
)

REM Set default port (override with: set PORT=5001)
if "%PORT%"=="" set PORT=5000
if "%HOST%"=="" set HOST=0.0.0.0

echo [INFO] Starting service on http://%HOST%:%PORT%
echo [INFO] Health check: http://127.0.0.1:%PORT%/health
echo [INFO] Extract endpoint: http://127.0.0.1:%PORT%/extract
echo.
echo [INFO] In Dify Code Node, set frame_service_url to:
echo        http://^<THIS_MACHINE_IP^>:%PORT%
echo.
echo Press Ctrl+C to stop the service.
echo.

python frame_extraction_service.py
pause
