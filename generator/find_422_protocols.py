# -*- coding: utf-8 -*-
"""查找数据协议文件夹中的 RS422 协议文件"""
import os
import re

base_dir = r"C:\Users\wangz\Desktop\协议\数据协议"

# RS422 相关关键词
rs422_keywords = ['422', 'RS422', 'RS-422', '串口', '串行', 'UART', '惯导', 'IRS', '惯性']

# 排除的协议类型（明确是其他协议的）
exclude_keywords = ['429', 'ARINC429', 'ARINC-429', 'CAN', 'dbc']

def check_filename_for_422(filename):
    """检查文件名是否包含 422 相关关键词"""
    filename_upper = filename.upper()
    
    # 排除明确是其他协议的
    for kw in exclude_keywords:
        if kw.upper() in filename_upper:
            return False, "其他协议"
    
    # 检查是否包含 422 关键词
    for kw in rs422_keywords:
        if kw.upper() in filename_upper:
            return True, kw
    
    return None, "未知"

def scan_directory(directory):
    """扫描目录查找可能的 422 协议文件"""
    results = {
        'rs422': [],
        'arinc429': [],
        'can': [],
        'unknown': []
    }
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # 只处理文档文件
            if not filename.endswith(('.docx', '.doc', '.xlsx', '.xls', '.pdf')):
                continue
            
            # 跳过临时文件
            if filename.startswith('~$'):
                continue
            
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, directory)
            filename_upper = filename.upper()
            
            # 分类
            if 'ARINC429' in filename_upper or 'A429' in filename_upper or '-429' in filename_upper:
                results['arinc429'].append(rel_path)
            elif '.DBC' in filename_upper or 'CAN' in filename_upper:
                results['can'].append(rel_path)
            elif any(kw.upper() in filename_upper for kw in rs422_keywords):
                results['rs422'].append(rel_path)
            else:
                # 检查路径中是否有关键词
                path_upper = rel_path.upper()
                if 'IRS' in path_upper or '惯' in path_upper:
                    results['rs422'].append(rel_path)
                else:
                    results['unknown'].append(rel_path)
    
    return results

print("=" * 60)
print("  数据协议文件夹 - 协议类型分析")
print("=" * 60)

results = scan_directory(base_dir)

print(f"\n【RS422 协议文件】({len(results['rs422'])} 个)")
print("-" * 40)
for f in sorted(results['rs422']):
    print(f"  ✓ {f}")

print(f"\n【ARINC429 协议文件】({len(results['arinc429'])} 个)")
print("-" * 40)
for f in sorted(results['arinc429']):
    print(f"  ✓ {f}")

print(f"\n【CAN 协议文件】({len(results['can'])} 个)")
print("-" * 40)
for f in sorted(results['can']):
    print(f"  ✓ {f}")

print(f"\n【未明确分类】({len(results['unknown'])} 个)")
print("-" * 40)
for f in sorted(results['unknown'])[:20]:  # 只显示前20个
    print(f"  ? {f}")
if len(results['unknown']) > 20:
    print(f"  ... 还有 {len(results['unknown']) - 20} 个文件")

print("\n" + "=" * 60)
print("  总结")
print("=" * 60)
print(f"  RS422:     {len(results['rs422'])} 个文件")
print(f"  ARINC429:  {len(results['arinc429'])} 个文件")
print(f"  CAN:       {len(results['can'])} 个文件")
print(f"  未分类:    {len(results['unknown'])} 个文件")
