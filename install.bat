@echo off
title ERP Test Automation Framework - Installer
echo ============================================
echo   ERP Test Automation Framework Installer
echo ============================================
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.11 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo [1/3] Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)
echo [2/3] Installing Playwright browsers...
python -m playwright install chromium
echo [3/3] Verifying...
python -c "import PyQt5; print('PyQt5 OK')"
python -c "import playwright; print('Playwright OK')"
echo.
echo ============================================
echo   Installation Complete!
echo   To start:  python Main.py
echo ============================================
pause
