@echo off
chcp 65001 >nul

echo ========================================
echo   测试 LLM 模型连接
echo ========================================
echo.

cd /d "C:\Users\wangz\Desktop\协议\generator"

echo [1] 检查 Docker 容器...
docker ps --filter "name=arinc429-generator"

echo.
echo [2] 检查环境变量...
docker exec arinc429-generator printenv | findstr LLM

echo.
echo [3] 复制测试脚本...
docker cp test_llm_simple.py arinc429-generator:/app/

echo.
echo [4] 测试模型连接...
docker exec arinc429-generator python /app/test_llm_simple.py

echo.
echo ========================================
echo 按任意键退出...
pause >nul
