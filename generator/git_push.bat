@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   推送代码到 GitHub
echo ========================================
echo.

echo [1/6] 确保敏感文件不被提交...
REM 从 Git 暂存区移除敏感文件（如果之前不小心添加过）
git rm -r --cached .env 2>nul
git rm -r --cached data/uploads 2>nul

echo.
echo [2/6] 确保数据库文件被包含...
REM 强制添加数据库文件（即使在 .gitignore 中有通配规则）
git add -f data/arinc429.db

echo.
echo [3/6] 检查 Git 状态...
git status

echo.
echo [4/6] 添加所有更改...
git add -A

echo.
echo [5/6] 创建新提交...
git commit -m "feat: 完善权限系统和协议解析 - 修复viewer权限、优化LLM解析、添加进度显示、包含完整数据库"

echo.
echo [6/6] 推送到 GitHub...
git push origin main

echo.
echo ========================================
echo   推送完成！
echo ========================================
pause
