@echo off
chcp 65001 >nul
echo ========================================
echo   调试 Label 273 解析
echo ========================================

cd /d "%~dp0"

docker cp debug_label273.py arinc429-generator:/app/
docker exec arinc429-generator python /app/debug_label273.py

pause
