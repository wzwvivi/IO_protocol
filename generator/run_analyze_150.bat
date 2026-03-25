@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   分析 Label 150 结构
echo ========================================
echo.

python analyze_label150.py

echo.
pause
