#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker 容器启动脚本
确保数据库存在并启动应用
"""

import os
import shutil
import subprocess
import sys

# 路径配置
DATA_DIR = "/app/data"
DB_FILE = os.path.join(DATA_DIR, "arinc429.db")
SEED_DB = "/app/seed_data/arinc429.db"

def main():
    print("=" * 60)
    print("接口代码生成平台 - Docker 启动")
    print("=" * 60)
    print()
    
    # 1. 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"数据目录: {DATA_DIR}")
    
    # 2. 检查数据库是否存在
    if os.path.exists(DB_FILE):
        db_size = os.path.getsize(DB_FILE)
        print(f"✓ 数据库已存在: {DB_FILE}")
        print(f"  大小: {db_size / 1024:.1f} KB")
    else:
        print(f"数据库不存在: {DB_FILE}")
        
        # 检查种子数据库
        if os.path.exists(SEED_DB):
            print(f"从种子数据库初始化...")
            shutil.copy(SEED_DB, DB_FILE)
            db_size = os.path.getsize(DB_FILE)
            print(f"✓ 数据库初始化完成")
            print(f"  大小: {db_size / 1024:.1f} KB")
        else:
            print(f"⚠ 种子数据库不存在，将创建空数据库")
    
    print()
    print("=" * 60)
    print("启动 Flask 应用...")
    print("=" * 60)
    print()
    
    # 3. 启动 Flask 应用
    # 使用 exec 替换当前进程，确保信号正确传递
    os.execvp("python", ["python", "app.py"])

if __name__ == "__main__":
    main()
