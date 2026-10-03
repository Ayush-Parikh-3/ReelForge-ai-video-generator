Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ReelForge - AI Text to Video Studio" -ForegroundColor White
Write-Host "  Ultra-Clean, Safe Stock Footage, Voiceover & Subtitles" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting web server on http://localhost:8000..." -ForegroundColor Green

python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
