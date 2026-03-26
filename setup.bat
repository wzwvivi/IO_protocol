@echo off
chcp 65001 >nul
REM ============================================================
REM 接口代码生成平台 - Windows 安装脚本
REM ============================================================

echo ============================================================
echo 接口代码生成平台 - 自动安装
echo ============================================================
echo.

REM 检查 Python
echo 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYTHON_VERSION=%%i
echo [OK] 找到 Python %PYTHON_VERSION%

REM 创建虚拟环境
echo.
echo 创建虚拟环境...
if not exist "venv" (
    python -m venv venv
    echo [OK] 虚拟环境创建成功
) else (
    echo [OK] 虚拟环境已存在
)

REM 激活虚拟环境
echo.
echo 激活虚拟环境...
call venv\Scripts\activate.bat
echo [OK] 虚拟环境已激活

REM 安装依赖
echo.
echo 安装 Python 依赖...
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo [OK] 依赖安装完成

REM 创建必要目录
echo.
echo 创建必要目录...
if not exist "data" mkdir data
if not exist "output" mkdir output
echo [OK] 目录创建完成

REM 初始化数据库
echo.
echo 初始化数据库...
python seed_data\init_db.py

echo.
echo ============================================================
echo [OK] 安装完成！
echo ============================================================
echo.
echo 启动服务:
echo   venv\Scripts\activate
echo   python app.py
echo.
echo 或者使用 Docker:
echo   docker-compose up -d
echo.
echo 访问地址: http://localhost:5001
echo 默认账户: admin / admin123
echo ============================================================
echo.
pause
