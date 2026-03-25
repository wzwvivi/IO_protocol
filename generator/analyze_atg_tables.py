# -*- coding: utf-8 -*-
"""分析 5G ATG 文档的所有表格，看哪些是 Label 表格"""
import os
import sys
import re

sys.path.insert(0, '/app')

from document_extractors import extract_word

uploads_dir = '/app/data/uploads'
atg_files = [f for f in os.listdir(uploads_dir) if 'ATG' in f.upper() and f.endswith('.docx')]

if not atg_files:
    print("未找到 ATG 文件")
    sys.exit(1)

filepath = os.path.join(uploads_dir, atg_files[0])
print(f"分析文件: {atg_files[0]}\n")

result = extract_word(filepath)
print(f"总表格数: {len(result.tables)}\n")

label_tables = []
non_label_tables = []

for i, table in enumerate(result.tables):
    # 将表格内容转为字符串用于搜索
    table_text = ' '.join([' '.join([str(cell) for cell in row]) for row in table])
    
    # 检查是否包含 Label 相关关键词
    has_label = bool(re.search(r'Label[_\s]*\d{3}|标\s*号', table_text, re.IGNORECASE))
    has_bit_def = bool(re.search(r'Bit\s*\d|位\s*定义|BNR|SSM|SDI', table_text, re.IGNORECASE))
    
    # 尝试提取 Label 号
    label_match = re.search(r'Label[_\s]*(\d{3})', table_text, re.IGNORECASE)
    label_num = label_match.group(1) if label_match else None
    
    # 获取表格预览
    preview = []
    for row in table[:2]:  # 前两行
        row_preview = [str(cell)[:25] for cell in row[:4]]  # 前4列，每列25字符
        preview.append(row_preview)
    
    info = {
        'index': i + 1,
        'rows': len(table),
        'cols': len(table[0]) if table else 0,
        'has_label': has_label,
        'has_bit_def': has_bit_def,
        'label_num': label_num,
        'preview': preview
    }
    
    if has_label or label_num:
        label_tables.append(info)
    else:
        non_label_tables.append(info)

print(f"=== Label 相关表格: {len(label_tables)} 个 ===")
for t in label_tables:
    print(f"  表格 {t['index']}: {t['rows']}x{t['cols']}, Label={t['label_num']}")
    for row in t['preview']:
        print(f"    {row}")

print(f"\n=== 非 Label 表格: {len(non_label_tables)} 个 ===")
for t in non_label_tables:
    print(f"  表格 {t['index']}: {t['rows']}x{t['cols']}")
    for row in t['preview']:
        print(f"    {row}")

# 统计唯一 Label
unique_labels = set(t['label_num'] for t in label_tables if t['label_num'])
print(f"\n=== 唯一 Label 数量: {len(unique_labels)} ===")
print(f"Labels: {sorted(unique_labels)}")

# 检查是否有重复 Label（同一个 Label 有多个表格）
from collections import Counter
label_counts = Counter(t['label_num'] for t in label_tables if t['label_num'])
duplicates = {k: v for k, v in label_counts.items() if v > 1}
if duplicates:
    print(f"\n=== 重复 Label（多个表格）===")
    for label, count in sorted(duplicates.items()):
        print(f"  Label {label}: {count} 个表格")
