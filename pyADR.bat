@echo off
call F:\ANACONDA\Scripts/activate.bat F:\ANACONDA\
cd C:\pyADR-main
rd /s /q __pycache__ 2>nul
F:\ANACONDA\python.exe C:\pyADR-main\NTNU_DataReduction.py
if errorlevel 1 (
    echo.
    echo pyADR exited with error code %errorlevel%.
    echo Press any key to close...
    pause >nul
)
