@echo off
chcp 65001 >nul
cd /d "%~dp0"
cd ..

echo ========================================
echo ARINC429 协议管理平台 - 上传到 GitHub
echo ========================================
echo.

REM 删除 git_repos 中的嵌套 .git 目录（防止子模块问题）
echo [1/7] 清理嵌套 Git 目录...
for /d %%i in (generator\git_repos\protocol-*) do (
    if exist "%%i\.git" rd /s /q "%%i\.git" 2>nul
)

echo [2/7] 检查 Git 状态...
git status --short

echo.
echo [3/7] 拉取远程更新...
git pull origin main --no-rebase 2>nul || echo 跳过拉取（可能是新仓库）

echo.
echo [4/7] 添加平台文件...

REM 根目录配置
git add .gitignore 2>nul
git add README.md 2>nul

REM generator 核心代码
git add generator/app.py
git add generator/database.py
git add generator/device_manager.py
git add generator/generator_core.py
git add generator/arinc429_runtime.py
git add generator/llm_parser.py
git add generator/document_extractors.py
git add generator/protocol_importer.py
git add generator/models.py
git add generator/entrypoint.py
git add generator/init_data.py
git add generator/init_users.py
git add generator/export_to_git.py

REM Git 存储模块
git add generator/git_storage/

REM 模板
git add generator/templates/

REM 数据（数据库和协议仓库）
git add -f generator/data/arinc429.db
git add -f generator/data/.gitkeep 2>nul
git add generator/git_repos/

REM 配置文件
git add generator/Dockerfile
git add generator/docker-compose.yml
git add generator/requirements.txt
git add generator/.dockerignore 2>nul
git add generator/.gitignore 2>nul

REM 文档
git add generator/README.md
git add generator/DEPLOY.md 2>nul
git add generator/ROLE_SYSTEM.md 2>nul

REM 部署脚本
git add generator/start.bat
git add generator/stop.bat
git add generator/setup.bat
git add generator/setup.sh
git add generator/git_push_all.bat 2>nul
git add generator/upload_to_github.bat

REM 配置示例
git add generator/example_protocol_config.json 2>nul
git add generator/protocol_schema.json 2>nul

REM output 目录结构
git add generator/output/.gitkeep 2>nul

echo.
echo [5/7] 查看将要提交的文件...
git status

echo.
set /p commit_msg="[6/7] 请输入提交说明 (直接回车使用默认): "
if "%commit_msg%"=="" set commit_msg=更新: ARINC429协议管理平台

echo.
echo 提交说明: %commit_msg%
git commit -m "%commit_msg%"

echo.
echo [7/7] 推送到 GitHub...
git push origin main

echo.
echo ========================================
if %errorlevel%==0 (
    echo ✓ 上传成功！
) else (
    echo × 上传失败，请检查错误信息
    echo.
    echo 如果是 non-fast-forward 错误，可以尝试:
    echo   git push origin main --force
)
echo ========================================
pause
