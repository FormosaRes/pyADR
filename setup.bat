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

REM ----- Find Python -----
REM Try (1) python in PATH; (2) common Anaconda install paths
set "PYTHON_EXE="

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto :run
)

REM Try common Anaconda locations
for %%P in (
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\Anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\Miniconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
    "C:\ProgramData\Anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "C:\Anaconda3\python.exe"
) do (
    if exist %%P (
        set "PYTHON_EXE=%%~P"
        goto :run
    )
)

echo [ERROR] Python not found.
echo.
echo Looked in PATH and these locations:
echo   %%USERPROFILE%%\anaconda3 / Anaconda3 / miniconda3 / Miniconda3
echo   C:\ProgramData\anaconda3 / Anaconda3 / miniconda3
echo   C:\Anaconda3
echo.
echo Solutions:
echo   1) Install Anaconda3 from https://www.anaconda.com/download
echo   2) Or open "Anaconda Prompt" from Start menu, cd to this folder,
echo      then run setup.bat there.
echo.
pause
exit /b 1

:run
echo Using Python: %PYTHON_EXE%
echo.
"%PYTHON_EXE%" "%~dp0install.py"

echo.
echo ========================================
echo  Installer finished. Press any key to close.
echo ========================================
pause >nul
