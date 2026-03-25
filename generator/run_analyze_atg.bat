@echo off
chcp 65001 >nul
echo ========================================
echo   分析 5G ATG 文档表格结构
echo ========================================
echo.

docker cp analyze_atg_tables.py arinc429-generator:/app/
docker exec arinc429-generator python /app/analyze_atg_tables.py

echo.
pause
