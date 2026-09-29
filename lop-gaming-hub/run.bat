@echo off
title LoP Gaming Hub
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
)

echo [2/4] Installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

echo [3/4] Seeding database and sample games...
python seed.py

echo [4/4] Starting server on http://127.0.0.1:5000
python app.py
pause