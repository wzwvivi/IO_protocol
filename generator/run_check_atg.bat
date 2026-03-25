@echo off
chcp 65001 >nul
echo ========================================
echo   检查 5G ATG 文档表格数量
echo ========================================
echo.

docker cp check_atg_tables.py arinc429-generator:/app/
docker exec arinc429-generator python /app/check_atg_tables.py

echo.
pause
