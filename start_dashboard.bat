@echo off
:: ============================================================
::  AI Job Application Agent Dashboard Runner
:: ============================================================
cd /d "%~dp0"
echo Starting AI Job Application Agent Dashboard...
.venv\Scripts\python.exe -m app.main
pause
