# -*- coding: utf-8 -*-
"""检查 5G ATG 文档的表格数量"""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, '/app')

from document_extractors import extract_word

# 查找 ATG 文件
uploads_dir = '/app/data/uploads'
atg_files = [f for f in os.listdir(uploads_dir) if 'ATG' in f.upper()]

print(f"找到 ATG 文件: {atg_files}")

for filename in atg_files:
    filepath = os.path.join(uploads_dir, filename)
    print(f"\n=== 分析文件: {filename} ===")
    
    result = extract_word(filepath)
    
    print(f"表格数量: {len(result.tables)}")
    print(f"段落数量: {len(result.paragraphs)}")
    
    # 显示每个表格的基本信息
    for i, table in enumerate(result.tables[:5]):  # 只显示前5个
        rows = len(table)
        cols = len(table[0]) if table else 0
        print(f"  表格 {i+1}: {rows} 行 x {cols} 列")
        if table:
            # 显示第一行作为预览
            first_row = [str(cell)[:20] for cell in table[0][:3]]
            print(f"    首行预览: {first_row}")
    
    if len(result.tables) > 5:
        print(f"  ... 还有 {len(result.tables) - 5} 个表格")
