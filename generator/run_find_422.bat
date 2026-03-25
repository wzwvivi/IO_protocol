@echo off
chcp 65001 >nul
echo ========================================
echo   查找 RS422 协议文件
echo ========================================
echo.

python find_422_protocols.py

echo.
pause
