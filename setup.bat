@echo off
REM ==========================================================
REM  pyADR v3.7 - One-click installer (Windows)
REM  Smart Python detection: Anaconda > PATH python > guide install
REM ==========================================================
echo.
echo ========================================
echo  pyADR v3.7 - One-click installer
echo ========================================
echo.

set "PYTHON_EXE="

REM ----- 1. Try common Anaconda locations FIRST (preferred) -----
for %%P in (
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\Anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\Miniconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
    "C:\ProgramData\Anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "C:\Anaconda3\python.exe"
    "C:\Anaconda\python.exe"
) do (
    if exist %%P (
        set "PYTHON_EXE=%%~P"
        echo [OK] Found Anaconda: %%~P
        goto :run
    )
)

REM ----- 2. Fallback: any Python on PATH -----
where python >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%X in ('where python') do set "PYTHON_EXE=%%X" & goto :path_found
)
goto :no_python

:path_found
echo [OK] Using Python in PATH: %PYTHON_EXE%
goto :run

REM ----- 3. No Python found - guide to install Anaconda -----
:no_python
echo.
echo ========================================
echo  Python / Anaconda not found
echo ========================================
echo.
echo pyADR requires Anaconda3 or Python 3.10+.
echo We strongly recommend Anaconda3 (easier setup).
echo.
echo Choose:
echo   [1] Open Anaconda download page in browser
echo   [2] Open Python.org download page
echo   [3] Exit (I'll install manually)
echo.
choice /c 123 /n /m "Your choice: "
if errorlevel 3 goto :end_fail
if errorlevel 2 (
    start https://www.python.org/downloads/
    goto :guide_after
)
start https://www.anaconda.com/download
:guide_after
echo.
echo ========================================
echo  After installation completes:
echo    1. Close all command prompt windows
echo    2. Re-run this setup.bat
echo ========================================
echo.
pause
exit /b 1

:end_fail
echo.
echo Aborted. Install Python 3.10+ then re-run setup.bat
echo.
pause
exit /b 1

REM ----- Run the installer -----
:run
echo.
"%PYTHON_EXE%" "%~dp0install.py"
set EXITCODE=%errorlevel%

echo.
echo ========================================
if %EXITCODE% == 0 (
    echo  Installation finished successfully.
    echo  Double-click pyADR.bat on your Desktop to launch.
) else (
    echo  Installer exited with code %EXITCODE%.
    echo  Scroll up to check for errors.
)
echo ========================================
echo Press any key to close this window.
pause >nul
