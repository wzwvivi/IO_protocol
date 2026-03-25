@echo off
chcp 65001 >nul
echo ========================================
echo   检查 LLM 配置状态
echo ========================================

echo.
echo [1] 检查容器是否运行...
docker ps --filter "name=arinc429-generator" --format "{{.Names}} - {{.Status}}"

echo.
echo [2] 检查 .env 文件...
if exist .env (
    echo .env 文件存在
    type .env | findstr LLM
) else (
    echo .env 文件不存在！
)

echo.
echo [3] 检查容器中的 LLM 环境变量...
docker exec arinc429-generator sh -c "echo LLM_API_BASE_URL: $LLM_API_BASE_URL"
docker exec arinc429-generator sh -c "echo LLM_MODEL: $LLM_MODEL"
docker exec arinc429-generator sh -c "echo LLM_API_KEY: ${LLM_API_KEY:0:20}..."
docker exec arinc429-generator sh -c "echo LLM_TIMEOUT: $LLM_TIMEOUT"

echo.
echo [4] 测试 LLM API 连接...
docker exec arinc429-generator python -c "
import os
api_key = os.environ.get('LLM_API_KEY', '')
api_base = os.environ.get('LLM_API_BASE_URL', '')
model = os.environ.get('LLM_MODEL', '')
print(f'API Key 已配置: {bool(api_key)}')
print(f'API Base: {api_base}')
print(f'Model: {model}')
if api_key:
    import urllib.request
    import json
    import ssl
    ctx = ssl.create_default_context()
    url = f'{api_base}/chat/completions'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    data = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': 'Hi'}], 'max_tokens': 5}).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            print('LLM API 连接成功!')
    except Exception as e:
        print(f'LLM API 连接失败: {e}')
"

echo.
echo ========================================
pause
