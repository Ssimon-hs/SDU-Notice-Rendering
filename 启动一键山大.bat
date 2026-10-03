@echo off
setlocal
cd /d "%~dp0"
title YJSD Launcher (safe)

echo ============================================
echo   YIJIAN SDU Launcher (safe, v0.5.1)
echo   Only starts this program. Never kills any
echo   other running process or closes your apps.
echo ============================================
echo.

rem ---------------------------------------------------------------
rem  First-run guard: if .venv is missing, run setup instead of
rem  failing with an error.
rem ---------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo [HINT] First run detected: Python environment not ready.
  echo        Auto-launching first-time setup, please wait a few
  echo        minutes. Next time this window will start directly.
  echo.
  call "%~dp0°²×°ÒÀÀµ.bat"
  goto :end
)

rem ---------------------------------------------------------------
rem  Build frontend if missing (this project's own dist)
rem ---------------------------------------------------------------
if not exist "dist\index.html" (
  echo [1/2] dist not found, building frontend ...
  where node >nul 2>nul
  if %errorlevel%==0 (
    call npm install >nul 2>&1
    if %errorlevel%==0 call npm run build
  ) else (
    echo [WARN] Node.js not found. dist missing.
  )
)

echo [2/2] Launching via safe PowerShell starter (no taskkill) ...
echo.

rem ---------------------------------------------------------------
rem  Launch through start-safe.ps1: auto-pick a free port,
rem  start uvicorn backend only, then open the browser.
rem ---------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-safe.ps1" -BasePort 8765

echo.
:end
pause
endlocal
