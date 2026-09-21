@echo off
REM ============================================================
REM  AI Resume Job Finder - Daily Runner
REM  Double-click this file OR let Task Scheduler run it daily
REM ============================================================

SET PYTHONUTF8=1
SET PYTHON=C:\Users\rajar\.gemini\antigravity\scratch\neon-assistant\.venv\Scripts\python.exe
SET SCRIPT_DIR=%~dp0

echo.
echo  [AI Job Finder] Starting daily job search...
echo  Time: %date% %time%
echo.

cd /d "%SCRIPT_DIR%"
"%PYTHON%" agent.py

echo.
echo  Press any key to exit...
pause > nul
