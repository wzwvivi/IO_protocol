@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   查看 32-3 设备的 Label 数据结构
echo ========================================
echo.

docker cp check_32_3.py arinc429-generator:/app/check_32_3.py
docker exec arinc429-generator python /app/check_32_3.py

echo.
pause
