@echo off
chcp 65001 >nul
echo ============================================================
echo 接口代码生成平台 - Docker 启动脚本
echo ============================================================
echo.

:: 检查 Docker 是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

echo [1/3] 构建 Docker 镜像...
docker-compose build

echo.
echo [2/3] 启动容器...
docker-compose up -d

echo.
echo [3/3] 完成!
echo.
echo ============================================================
echo 平台已启动，请访问: http://localhost:5001
echo 默认账户: admin / admin123
echo.
echo 生成的文件会保存在: %~dp0output\
echo.
echo 停止服务请运行: docker-compose down
echo ============================================================
echo.
pause
