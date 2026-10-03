@echo off
setlocal
cd /d "%~dp0"
title YJSD Launcher

echo ============================================
echo            YIJIAN SDU Launcher (v0.5)
echo ============================================
echo.

echo [1/4] Releasing ports 8765 / 5173 if occupied ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":8765 .*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":5173 .*LISTENING"') do taskkill /f /pid %%a >nul 2>&1

echo [2/4] Checking Python environment ...
set "PY=.venv\Scripts\python.exe"
set "NEED_INSTALL=0"
if not exist "%PY%" (
  echo     No venv found. Creating .venv and installing dependencies, first run takes a while ...
  python -m venv .venv
  set "NEED_INSTALL=1"
) else (
  "%PY%" -c "import uvicorn, fastapi, bs4, requests" >nul 2>&1
  if errorlevel 1 (
    echo     Dependencies incomplete. Reinstalling ...
    set "NEED_INSTALL=1"
  )
)
if "%NEED_INSTALL%"=="1" (
  "%PY%" -m pip install --upgrade pip >nul 2>&1
  "%PY%" -m pip install -r server\requirements.txt
  if errorlevel 1 (
    echo.
    echo [ERROR] Dependency install failed. Check your network and run this again.
    echo.
    pause
    exit /b 1
  )
)

echo [3/4] Checking frontend build ...
if not exist "dist\index.html" (
  where node >nul 2>nul
  if %errorlevel%==0 (
    echo     Building frontend, first run takes a while ...
    call npm install
    if errorlevel 1 (
      echo [WARN] npm install failed.
    ) else (
      call npm run build
    )
  ) else (
    echo [WARN] Node.js not found. Please install Node.js and run this again.
    pause
    exit /b 1
  )
)

echo [4/4] Starting backend, logs go to server.log ...
if exist server.log del /f /q server.log >nul 2>&1
start "" /min cmd /c "%PY% -m uvicorn server.main:app --host 127.0.0.1 --port 8765 > server.log 2>&1"

echo     Waiting for backend, up to about 60 seconds ...
set /a retry=0
:wait
timeout /t 2 >nul
set /a retry+=1
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8765/api/health -TimeoutSec 3).StatusCode } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  if %retry% lss 30 goto wait
  echo.
  echo [FAIL] Backend did not start. Content of server.log:
  echo ============================================
  type server.log
  echo ============================================
  echo.
  pause
  exit /b 1
)

start http://127.0.0.1:8765
echo.
echo ============================================
echo   YIJIAN SDU is running:  http://127.0.0.1:8765
echo   First open shows the onboarding guide page.
echo   To stop: run the stop .bat in this folder,
echo   or close the minimized backend window.
echo ============================================
echo.
timeout /t 8 >nul
endlocal
exit
