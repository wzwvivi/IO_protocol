@echo off
chcp 65001 >nul
echo ========================================
echo   调试 LLM 输出和转换过程
echo ========================================

cd /d "%~dp0"

docker cp debug_llm_output.py arinc429-generator:/app/
docker exec arinc429-generator python /app/debug_llm_output.py

pause
