@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   重建 Docker 并测试 Label 150 解析
echo ========================================
echo.

echo [1/3] 重建 Docker 镜像...
docker-compose down
docker-compose up --build -d

echo.
echo [2/3] 等待容器启动...
timeout /t 10 /nobreak >nul

echo.
echo [3/3] 测试 LLM 解析...
docker cp debug_parse.py arinc429-generator:/app/debug_parse.py 2>nul
docker exec arinc429-generator python /app/debug_parse.py

echo.
echo ========================================
echo   完成！
echo ========================================
pause
