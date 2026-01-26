@echo off
setlocal

cd /d %~dp0
set LOG=%~dp0launch.log
echo [launch] %date% %time% > "%LOG%"

if not exist venv\Scripts\python.exe (
  echo [launch] venv missing, running install... >> "%LOG%"
  call install.bat >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo Install failed. See launch.log for details.
    type "%LOG%"
    pause
    exit /b 1
  )
)

venv\Scripts\python.exe -c "import dotenv" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [launch] dependencies missing, running install... >> "%LOG%"
  call install.bat >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo Install failed. See launch.log for details.
    type "%LOG%"
    pause
    exit /b 1
  )
)

venv\Scripts\python.exe gui.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Launch failed. See launch.log for details.
  type "%LOG%"
  pause
  exit /b 1
)

endlocal
