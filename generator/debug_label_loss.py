# -*- coding: utf-8 -*-
"""
调试 Label 丢失问题
对比预解析和 LLM 解析的 Label 数量
"""

import os
import sys
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_extractors import extract_word, extract_excel, preparse_arinc429_table, build_llm_prompt_context_v2
from llm_parser import parse_protocol_with_llm, get_system_prompt

def main():
    # 查找上传的文件
    upload_dir = os.path.join(os.path.dirname(__file__), 'data', 'uploads')
    
    if not os.path.exists(upload_dir):
        print(f"上传目录不存在: {upload_dir}")
        return
    
    # 找到最新的 docx 文件
    files = [f for f in os.listdir(upload_dir) if f.endswith('.docx')]
    if not files:
        print("没有找到 .docx 文件")
        return
    
    print(f"=== 找到 {len(files)} 个 docx 文件 ===")
    for f in files[:5]:
        print(f"  - {f}")
    
    # 测试第一个文件
    test_file = os.path.join(upload_dir, files[0])
    print(f"\n=== 测试文件: {files[0]} ===")
    
    # 1. 提取文档内容
    print("\n【步骤1】提取文档内容...")
    result = extract_word(test_file)
    print(f"  段落数: {len(result.paragraphs)}")
    print(f"  表格数: {len(result.tables)}")
    
    # 2. 预解析 Labels
    print("\n【步骤2】预解析 Labels...")
    preparsed_labels = []
    for table in result.tables:
        labels = preparse_arinc429_table(table)
        preparsed_labels.extend(labels)
    
    # 去重
    seen = set()
    unique_preparsed = []
    for label in preparsed_labels:
        if label['label_oct'] not in seen:
            seen.add(label['label_oct'])
            unique_preparsed.append(label)
    
    print(f"  预解析出 {len(preparsed_labels)} 个 Labels（去重前）")
    print(f"  预解析出 {len(unique_preparsed)} 个 Labels（去重后）")
    
    # 显示预解析的 Label 列表
    print("\n  预解析的 Label 列表:")
    preparsed_octs = sorted([l['label_oct'] for l in unique_preparsed])
    print(f"  {preparsed_octs}")
    
    # 3. 构建 LLM 上下文
    print("\n【步骤3】构建 LLM 上下文...")
    context = build_llm_prompt_context_v2(result, max_chars=100000)
    print(f"  上下文长度: {len(context)} 字符")
    
    # 4. 调用 LLM 解析
    print("\n【步骤4】调用 LLM 解析...")
    config = {
        'api_key': os.environ.get('LLM_API_KEY', ''),
        'api_base': os.environ.get('LLM_API_BASE_URL', ''),
        'model': os.environ.get('LLM_MODEL', '')
    }
    print(f"  API: {config['api_base']}")
    print(f"  Model: {config['model']}")
    print(f"  API Key: {'已配置' if config['api_key'] else '未配置'}")
    
    if not config['api_key']:
        print("  ⚠️ API Key 未配置，跳过 LLM 解析")
        return
    
    llm_result, errors = parse_protocol_with_llm(context, unique_preparsed, '429')
    
    if errors:
        print(f"  LLM 错误: {errors}")
    
    # 5. 对比结果
    llm_labels = llm_result.get('labels', [])
    print(f"\n【步骤5】对比结果")
    print(f"  预解析 Labels: {len(unique_preparsed)}")
    print(f"  LLM 返回 Labels: {len(llm_labels)}")
    
    # 找出丢失的 Labels
    llm_octs = set(l.get('label_oct', '') for l in llm_labels)
    preparsed_octs_set = set(preparsed_octs)
    
    missing = preparsed_octs_set - llm_octs
    extra = llm_octs - preparsed_octs_set
    
    print(f"\n  丢失的 Labels ({len(missing)}): {sorted(missing)}")
    print(f"  新增的 Labels ({len(extra)}): {sorted(extra)}")
    
    # 显示 LLM 返回的 Labels
    print("\n  LLM 返回的 Label 列表:")
    llm_octs_sorted = sorted([l.get('label_oct', '???') for l in llm_labels])
    print(f"  {llm_octs_sorted}")
    
    # 6. 检查 LLM 返回的 Labels 是否有字段定义
    print("\n【步骤6】检查 LLM 返回的 Labels 字段定义")
    empty_count = 0
    for label in llm_labels[:10]:  # 只显示前10个
        has_bnr = len(label.get('bnr_fields', [])) > 0
        has_discrete = len(label.get('discrete_bits', {})) > 0
        has_special = len(label.get('special_fields', [])) > 0
        
        if not has_bnr and not has_discrete and not has_special:
            empty_count += 1
            print(f"  ⚠️ Label {label.get('label_oct')}: 无字段定义")
        else:
            print(f"  ✓ Label {label.get('label_oct')}: BNR={has_bnr}, Discrete={has_discrete}, Special={has_special}")
    
    print(f"\n  空字段 Labels: {empty_count}/{len(llm_labels)}")

if __name__ == '__main__':
    main()
