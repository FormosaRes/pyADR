@echo off
call F:\ANACONDA\Scripts/activate.bat F:\ANACONDA\
cd C:\pyADR-main
rd /s /q __pycache__ 2>nul
echo ===== Running debug_pyadr.py (CalcT0Page test) =====
F:\ANACONDA\python.exe debug_pyadr.py
pause
