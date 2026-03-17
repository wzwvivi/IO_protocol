@echo off
chcp 65001
echo ========================================
echo ARINC429 Generator - Push to GitHub
echo ========================================

cd /d "%~dp0"

echo.
echo [1/7] 配置 Git 用户信息...
git config user.email "wzwvivi@users.noreply.github.com"
git config user.name "wzwvivi"

echo.
echo [2/7] 初始化 Git 仓库...
if exist ".git" (
    echo Git 仓库已存在，跳过初始化
) else (
    git init
)

echo.
echo [3/7] 添加所有文件...
git add -A

echo.
echo [4/7] 查看状态...
git status

echo.
echo [5/7] 提交代码...
git commit -m "Initial commit: ARINC429 协议解析代码生成器"

echo.
echo [6/7] 配置远程仓库...
git remote remove origin 2>nul
git remote add origin https://github.com/wzwvivi/-.git

echo.
echo [7/7] 推送到 GitHub...
git branch -M main
git push -u origin main

echo.
echo ========================================
if %errorlevel% equ 0 (
    echo 成功！请访问 https://github.com/wzwvivi/-
) else (
    echo 推送失败，请检查错误信息
)
echo ========================================
pause
