# -*- coding: utf-8 -*-
"""分析 ATG 文档中 Label 150 的详细结构"""
import os
import sys
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_extractors import extract_document

def main():
    # 原始文档路径
    doc_path = r"C:\Users\wangz\Desktop\协议\数据协议\ATA23-通信系统\23-3-5GATG\5G ATG CPE P4800 ARINC429通信协议-V1.0.docx"
    
    if not os.path.exists(doc_path):
        print(f"文件不存在: {doc_path}")
        return
    
    print(f"分析文件: {doc_path}")
    print("=" * 80)
    
    result = extract_document(doc_path)
    print(f"段落数: {len(result.paragraphs)}")
    print(f"表格数: {len(result.tables)}")
    
    # 查找所有包含 "150" 的表格
    print("\n" + "=" * 80)
    print("搜索 Label 150 相关表格")
    print("=" * 80)
    
    label_150_tables = []
    
    for i, table in enumerate(result.tables):
        rows = table.get('rows', [])
        table_has_150 = False
        
        for row in rows:
            cells = row.get('cells', [])
            row_text = ' '.join(str(c) for c in cells)
            
            # 检查是否包含 Label 150
            if '150' in row_text:
                # 检查是否是 Label 定义（而不是其他数字）
                if any(kw in row_text.lower() for kw in ['label', '标号', '规范号', 'bit', '位']):
                    table_has_150 = True
                    break
        
        if table_has_150:
            label_150_tables.append((i, table))
    
    print(f"\n找到 {len(label_150_tables)} 个包含 Label 150 的表格")
    
    # 详细打印每个相关表格
    for idx, table in label_150_tables:
        print(f"\n{'='*80}")
        print(f"表格 {idx + 1}")
        print(f"{'='*80}")
        
        rows = table.get('rows', [])
        for j, row in enumerate(rows):
            cells = row.get('cells', [])
            # 高亮包含 150 的行
            row_text = ' | '.join(str(c)[:40] for c in cells)
            if '150' in row_text:
                print(f">>> 行{j}: {row_text}")
            else:
                print(f"    行{j}: {row_text}")
    
    # 分析 Label 150 的位定义结构
    print("\n" + "=" * 80)
    print("分析 Label 150 的位定义")
    print("=" * 80)
    
    # 查找位定义表格（通常紧跟在 Label 定义之后）
    for idx, table in label_150_tables:
        rows = table.get('rows', [])
        
        # 检查是否是位定义表格
        has_bit_def = False
        for row in rows:
            cells = row.get('cells', [])
            row_text = ' '.join(str(c) for c in cells).lower()
            if any(kw in row_text for kw in ['bit', '位', 'msb', 'lsb', '数据位', '符号位']):
                has_bit_def = True
                break
        
        if has_bit_def:
            print(f"\n表格 {idx + 1} 包含位定义:")
            for j, row in enumerate(rows):
                cells = row.get('cells', [])
                print(f"  {cells}")
    
    # 打印所有表格的简要信息
    print("\n" + "=" * 80)
    print("所有表格概览")
    print("=" * 80)
    
    for i, table in enumerate(result.tables):
        rows = table.get('rows', [])
        if rows:
            first_row = rows[0].get('cells', [])
            first_row_text = ' | '.join(str(c)[:20] for c in first_row[:5])
            print(f"表格 {i+1}: {len(rows)} 行, 首行: {first_row_text}")

if __name__ == '__main__':
    main()
