# ARINC429 协议代码生成平台 - Docker 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .
COPY generator_core.py .
COPY arinc429_runtime.py .
COPY example_protocol_config.json .
COPY protocol_schema.json .
COPY init_data.py .
COPY templates/ templates/

# 创建必要目录
RUN mkdir -p /app/output /app/data

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]
