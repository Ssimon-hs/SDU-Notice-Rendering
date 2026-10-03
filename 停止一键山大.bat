@echo off
chcp 65001 >nul
echo Stopping YJSD (release 5173 / 8765) ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":5173 .*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":8765 .*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
echo Stopped. You can close this window.
timeout /t 3 >nul
exit
