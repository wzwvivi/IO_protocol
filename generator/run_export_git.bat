@echo off
chcp 65001 >nul
echo.
echo ARINC429 协议平台 - 数据库导出到 Git
echo ========================================
echo.

cd /d "%~dp0"

python export_to_git.py %*

echo.
pause
