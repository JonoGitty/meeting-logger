@echo off
setlocal

cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.10+ first.
  echo You can try: winget install -e --id Python.Python.3.11
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg not found. Installing via winget...
  winget install -e --id Gyan.FFmpeg
  if errorlevel 1 (
    echo FFmpeg install failed. Install manually and re-run.
    exit /b 1
  )
)

if not exist venv (
  python -m venv venv
)

venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

echo Setup complete.
endlocal
