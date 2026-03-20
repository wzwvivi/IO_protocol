@echo off
chcp 65001 >nul
echo 正在停止接口代码生成平台...
docker-compose down
echo 已停止
pause
