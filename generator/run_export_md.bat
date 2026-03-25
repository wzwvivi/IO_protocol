@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   导出 Markdown 转换结果
echo ========================================
echo.

docker cp export_md.py arinc429-generator:/app/export_md.py
docker exec arinc429-generator python /app/export_md.py

echo.
echo 复制 MD 文件到本地...
docker cp arinc429-generator:/app/data/extracted_content.md data/extracted_content.md

echo.
echo MD 文件已保存到: data\extracted_content.md
echo.
pause
