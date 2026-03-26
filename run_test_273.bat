@echo off
chcp 65001 >nul
echo ========================================
echo   测试 Label 273 解析
echo ========================================

cd /d "%~dp0"

docker cp test_label_273.py arinc429-generator:/app/
docker exec arinc429-generator python /app/test_label_273.py

echo.
pause
