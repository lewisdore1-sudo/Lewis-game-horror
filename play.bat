@echo off
rem Double-click to play The Shifting Mansion.
cd /d "%~dp0"
python main.py
if errorlevel 1 pause
