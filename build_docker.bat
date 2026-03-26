@echo off
chcp 65001 >nul
echo ============================================================
echo 构建 Docker 镜像（包含完整数据库）
echo ============================================================
echo.

cd /d "%~dp0"

echo 步骤 1/3: 检查数据库...
if not exist "data\arinc429.db" (
    echo 数据库不存在，正在构建...
    python build_full_db.py
    if %ERRORLEVEL% NEQ 0 (
        echo 构建数据库失败！
        pause
        exit /b 1
    )
) else (
    echo ✓ 数据库已存在
    for %%A in ("data\arinc429.db") do echo   大小: %%~zA bytes
)

echo.
echo 步骤 2/3: 停止旧容器...
docker-compose down 2>nul

echo.
echo 步骤 3/3: 构建并启动 Docker 镜像...
docker-compose up --build -d

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo ✓ 构建完成！
    echo.
    echo 访问地址: http://localhost:5001
    echo 默认账户: admin / admin123
    echo.
    echo 常用命令:
    echo   查看日志: docker-compose logs -f
    echo   停止服务: docker-compose down
    echo   重启服务: docker-compose restart
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo ❌ 构建失败！请检查 Docker 是否正在运行
    echo ============================================================
)

pause
