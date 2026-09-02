@echo off
title Fix and start AI Studio
echo Closing any old studio still running...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*serve.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 2 /nobreak >nul
echo Starting the new studio from C:\Users\julia\AiStudio ...
start "AI Studio" /D "C:\Users\julia\AiStudio" "C:\Users\julia\AiStudio\start-studio.cmd"
timeout /t 8 /nobreak >nul
echo Opening the Productions page in your browser...
start "" "http://127.0.0.1:8765/cb-studio/app.html"
echo.
echo Done. You can close this window. Leave the "AI Studio" window open while you work.
pause
