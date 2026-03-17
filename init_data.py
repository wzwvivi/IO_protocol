#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化数据目录
首次运行时创建必要的目录和默认配置
"""

import os
import json
import shutil

def init_data_directory():
    """初始化数据目录"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    output_dir = os.path.join(script_dir, 'output')
    
    # 创建目录
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # 如果配置文件不存在，复制示例配置
    config_path = os.path.join(data_dir, 'protocol_config.json')
    example_path = os.path.join(script_dir, 'example_protocol_config.json')
    
    if not os.path.exists(config_path) and os.path.exists(example_path):
        shutil.copy(example_path, config_path)
        print(f'已创建默认配置: {config_path}')
    
    print('数据目录初始化完成')
    print(f'  数据目录: {data_dir}')
    print(f'  输出目录: {output_dir}')

if __name__ == '__main__':
    init_data_directory()
