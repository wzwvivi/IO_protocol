@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo   设置 LLM API Key
echo ========================================

REM 创建 .env 文件（请替换为你自己的 OpenAI API Key）
echo LLM_API_KEY=your-openai-api-key-here > .env

echo .env 文件已创建！
echo.
echo 现在重建 Docker...
docker-compose down
docker-compose up --build -d

echo.
echo ========================================
echo   完成！LLM 已配置
echo ========================================
pause
