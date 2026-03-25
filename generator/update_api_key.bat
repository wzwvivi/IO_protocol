@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo 更新 OpenAI API Key
echo ========================================

REM 请替换为你自己的 OpenAI API Key
echo LLM_API_KEY=your-openai-api-key-here> .env

echo .env 文件已更新!
echo.

echo ========================================
echo 重建 Docker 容器
echo ========================================
docker-compose down
docker-compose up --build -d

echo.
echo ========================================
echo 完成！请等待几秒后刷新网页
echo ========================================
pause
