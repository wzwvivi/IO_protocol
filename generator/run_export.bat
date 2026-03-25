@echo off
chcp 65001 >nul
cd /d "%~dp0"
python export_to_git.py
pause
