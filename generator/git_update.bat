@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo 更新 GitHub 仓库
echo https://github.com/wzwvivi/IO_protocol
echo ============================================
echo.

echo [1/6] 检查 Git 状态...
git status
echo.

echo [2/6] 强制添加数据库文件（确保被追踪）...
git add -f data/arinc429.db
if errorlevel 1 (
    echo 警告：添加数据库文件失败，请检查文件是否存在
)
echo.

echo [3/6] 添加所有更改的文件...
git add -A
echo.

echo [4/6] 查看将要提交的更改...
git status
echo.

echo [5/6] 提交更改...
git commit -m "更新：添加数据库文件，修复部署问题，更新README"
echo.

echo [6/6] 推送到 GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo 推送失败，尝试使用 master 分支...
    git push origin master
)
echo.

echo ============================================
echo 完成！请检查 GitHub 仓库确认更新
echo https://github.com/wzwvivi/IO_protocol
echo ============================================
pause
