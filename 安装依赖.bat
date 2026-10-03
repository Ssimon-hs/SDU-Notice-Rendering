@echo off
setlocal
cd /d "%~dp0"
title yijian-sdu first-time setup

echo ============================================
echo   YIJIAN SDU  /  first-time setup
echo   Run this ONCE before launching the app.
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERROR] Python not found. Install Python 3.10+ first:
  echo         https://www.python.org/downloads/
  pause
  exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERROR] Node.js not found. Install Node.js 18+ first:
  echo         https://nodejs.org/
  pause
  exit /b 1
)

echo [1/4] Creating Python virtual environment .venv ...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if %errorlevel% neq 0 (
  echo [ERROR] Failed to create .venv
  pause
  exit /b 1
)

echo [2/4] Installing backend dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
  echo [WARN] Default source failed, retrying with Aliyun mirror ...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q -i https://mirrors.aliyun.com/pypi/simple/
)
if %errorlevel% neq 0 (
  echo [ERROR] Backend dependencies failed to install.
  pause
  exit /b 1
)

echo [3/4] Installing frontend dependencies ...
call npm install
if %errorlevel% neq 0 (
  echo [ERROR] npm install failed. Try a mirror:
  echo         npm config set registry https://registry.npmmirror.com
  pause
  exit /b 1
)

echo [4/4] Building frontend to dist\ ...
call npm run build
if %errorlevel% neq 0 (
  echo [ERROR] Frontend build failed.
  pause
  exit /b 1
)

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo.
  echo [NOTE] Created .env from .env.example
  echo        Open it and set your own COMMUNITY_ADMIN_PASSWORD,
  echo        otherwise the admin moderation panel stays locked.
)

echo.
echo ============================================
echo   Setup complete.
echo   Double-click START-LAUNCH.bat to run.
echo   ?????????????????????.bat?????¨À?
echo ============================================
echo.
pause
endlocal
