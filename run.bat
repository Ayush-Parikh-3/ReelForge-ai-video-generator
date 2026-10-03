@echo off
title ReelForge - AI Text to Video Studio
echo ========================================================
echo   ReelForge - AI Text to Video Studio
echo   Ultra-Clean, Safe Stock Footage, Voiceover & Subtitles
echo ========================================================
echo.

python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
pause
