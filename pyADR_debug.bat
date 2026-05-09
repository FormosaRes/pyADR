@echo off
call F:\ANACONDA\Scripts/activate.bat F:\ANACONDA\
cd C:\pyADR-main
rd /s /q __pycache__ 2>nul
F:\ANACONDA\python.exe debug_pyadr2.py
pause
