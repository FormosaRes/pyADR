@echo off
REM ==========================================================
REM  pyADR v3.7 - One-click installer (Windows)
REM  Double-click this file to install.
REM ==========================================================
echo.
echo ========================================
echo  pyADR v3.7 - One-click installer
echo ========================================
echo.

REM Check if Python is available
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo.
    echo Please install Anaconda3 from:
    echo   https://www.anaconda.com/download
    echo Then re-run setup.bat from the Anaconda PowerShell Prompt.
    echo.
    pause
    exit /b 1
)

REM Run install.py
python "%~dp0install.py"

echo.
pause
