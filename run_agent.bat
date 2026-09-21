@echo off
:: ============================================================
::  AI Resume Job Finder - Automated Runner Batch Script
:: ============================================================
cd /d "%~dp0"
echo [%date% %time%] Starting AI Resume Job Finder... >> agent_runner.log

:: Add uv to PATH if needed
set PATH=%USERPROFILE%\.cargo\bin;%USERPROFILE%\.local\bin;%PATH%

uv run python agent.py >> agent_runner.log 2>&1

echo [%date% %time%] AI Resume Job Finder finished with exit code %errorlevel% >> agent_runner.log
