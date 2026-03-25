@echo off
chcp 65001 >nul
echo ========================================
echo   调试 Label 丢失问题
echo ========================================

cd /d "%~dp0"

docker cp debug_label_loss.py arinc429-generator:/app/
docker exec arinc429-generator python /app/debug_label_loss.py

echo.
pause
