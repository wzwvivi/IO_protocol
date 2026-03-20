@echo off
chcp 65001 >nul
echo ============================================================
echo 构建 Docker 镜像（包含完整数据库）
echo ============================================================
echo.

echo 步骤 1/4: 检查数据库...
if not exist "data\arinc429.db" (
    echo 数据库不存在，正在构建...
    python build_full_db.py
    if %ERRORLEVEL% NEQ 0 (
        echo 构建数据库失败！
        pause
        exit /b 1
    )
) else (
    echo 数据库已存在，跳过构建。如需重置请删除 data\arinc429.db
)

echo.
echo 步骤 2/4: 验证数据库完整性...
python verify_system.py
if %ERRORLEVEL% NEQ 0 (
    echo 数据库验证失败！
    pause
    exit /b 1
)

echo.
echo 步骤 3/4: 停止旧容器...
docker-compose down 2>nul

echo.
echo 步骤 4/4: 构建并启动 Docker 镜像...
docker-compose up --build -d

echo.
echo ============================================================
echo 构建完成！
echo.
echo 访问地址: http://localhost:5001
echo 默认账户: admin / admin123
echo.
echo 重要提示:
echo - 数据保存在 ./data 目录，Docker 重启后数据不会丢失
echo - 如需完全重置，请删除 data\arinc429.db 后重新运行此脚本
echo.
echo 常用命令:
echo   查看日志: docker-compose logs -f
echo   停止服务: docker-compose down
echo   重启服务: docker-compose restart
echo ============================================================
pause
