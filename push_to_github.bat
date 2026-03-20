@echo off
chcp 65001 >nul
echo ============================================================
echo 推送到 GitHub
echo ============================================================
echo.

cd /d "C:\Users\wangz\Desktop\协议\generator"

echo 当前目录: %CD%
echo.

REM 检查数据库文件是否存在
if not exist "data\arinc429.db" (
    echo ❌ 错误: 数据库文件不存在！
    pause
    exit /b 1
)

echo ✓ 数据库文件存在
echo.

REM 删除旧的 .git 目录（如果存在）
if exist ".git" (
    echo 删除旧的 Git 配置...
    rmdir /s /q ".git"
)

REM 重新初始化 Git
echo 初始化 Git 仓库...
git init
git branch -M main

REM 配置 Git（避免警告）
git config user.email "wzwvivi@users.noreply.github.com"
git config user.name "wzwvivi"

REM 添加所有文件
echo.
echo 添加文件...
git add -A

REM 显示状态
echo.
echo 将要提交的文件:
git status --short
echo.

REM 提交
echo 提交更改...
git commit -m "更新: 完整数据库、版本管理、清理测试文件"

REM 设置远程仓库
git remote remove origin 2>nul
git remote add origin https://github.com/wzwvivi/IO_protocol.git

REM 强制推送
echo.
echo 推送到 GitHub (强制覆盖)...
git push -u origin main --force

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo ✓ 推送成功！
    echo.
    echo GitHub 仓库: https://github.com/wzwvivi/IO_protocol
    echo.
    echo 请刷新 GitHub 页面确认更新！
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo ❌ 推送失败！请检查网络连接和 GitHub 认证
    echo ============================================================
)

pause
