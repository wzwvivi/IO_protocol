# 接口代码生成平台 - Docker 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 安装系统依赖（包括 Git）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 配置 Git（避免权限问题）
RUN git config --global user.email "system@protocol-platform.local" \
    && git config --global user.name "Protocol Platform" \
    && git config --global init.defaultBranch main

# 安装 Python 依赖
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

# 复制协议导入模块
COPY document_extractors.py .
COPY llm_parser.py .
COPY protocol_importer.py .

# 复制 Git 存储模块
COPY git_storage/ git_storage/
COPY export_to_git.py .

# 创建必要目录
RUN mkdir -p /app/output /app/data /app/seed_data /app/git_repos

# 复制预构建的完整数据库到 seed_data 目录（作为种子数据）
# 注意：构建镜像前需要先运行 python build_full_db.py
COPY data/arinc429.db /app/seed_data/arinc429.db

# 复制启动脚本（使用 Python 脚本确保跨平台兼容）
COPY entrypoint.py /app/entrypoint.py

# 暴露端口
EXPOSE 5000

# 使用 Python 启动脚本（会检查数据库是否存在，不存在则从种子数据复制）
CMD ["python", "entrypoint.py"]
