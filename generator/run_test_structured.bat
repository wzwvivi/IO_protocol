@echo off
chcp 65001 >nul
echo ========================================
echo   测试结构化数据提取
echo ========================================

cd /d "%~dp0"

docker cp document_extractors.py arinc429-generator:/app/
docker cp test_structured.py arinc429-generator:/app/
docker exec arinc429-generator python /app/test_structured.py

pause
