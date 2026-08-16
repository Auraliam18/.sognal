@echo off
REM حلقه زنده حمید — ویندوز: دوبار کلیک کن، همین.
cd /d "%~dp0"
git pull --rebase origin main 2>nul
cd claude-liam-signal\python
echo === حلقه زنده حمید — برای توقف پنجره را ببند ===
python -m hamid.live_service
pause
