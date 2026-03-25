@echo off
chcp 65001 >nul
cd /d "%~dp0"
cd ..

echo ========================================
echo 上传所有文件到 GitHub（包括 git_repos）
echo ========================================

echo.
echo [1/6] 检查 Git 状态...
git status

echo.
echo [2/6] 拉取远程更新...
git pull origin main --no-rebase

echo.
echo [3/6] 添加所有文件（包括 git_repos）...
git add -A
git add -f generator/git_repos/

echo.
echo [4/6] 查看将要提交的文件...
git status

echo.
echo [5/6] 提交更改...
git commit -m "v2.0.0: Git存储架构升级 - 完整版本历史和协议数据"

echo.
echo [6/6] 推送到 GitHub...
git push origin main

echo.
echo ========================================
echo 完成！
echo ========================================
pause
