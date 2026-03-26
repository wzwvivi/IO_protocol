@echo off
chcp 65001 >nul
echo ========================================
echo   PDF 转图片工具
echo ========================================
echo.

echo [1] 检查依赖库...
python -c "import fitz" 2>nul
if %errorlevel% neq 0 (
    echo PyMuPDF 未安装，正在安装...
    pip install PyMuPDF
    echo.
)

echo [2] 开始转换...
python pdf_to_images.py

echo.
echo ========================================
pause
