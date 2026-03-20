# 接口代码生成平台 - Docker 镜像
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
COPY database.py .
COPY models.py .
COPY device_manager.py .
COPY init_users.py .
COPY example_protocol_config.json .
COPY protocol_schema.json .
COPY init_data.py .
COPY templates/ templates/

# 创建必要目录
RUN mkdir -p /app/output /app/data /app/seed_data

# 复制预构建的完整数据库到 seed_data 目录（作为种子数据）
# 注意：构建镜像前需要先运行 python build_full_db.py
COPY data/arinc429.db /app/seed_data/arinc429.db

# 复制启动脚本（使用 Python 脚本确保跨平台兼容）
COPY entrypoint.py /app/entrypoint.py

# 暴露端口
EXPOSE 5000

# 使用 Python 启动脚本（会检查数据库是否存在，不存在则从种子数据复制）
CMD ["python", "entrypoint.py"]
