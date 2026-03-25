# -*- coding: utf-8 -*-
"""调试 Label 273 的解析"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_extractors import extract_word, convert_to_markdown, build_llm_prompt_context_v2, preparse_arinc429_table
from llm_parser import _call_llm_api, get_system_prompt

def main():
    upload_dir = '/app/data/uploads'
    
    files = os.listdir(upload_dir)
    docx_files = [f for f in files if f.endswith('.docx') and 'ATG' in f and not f.startswith('~')]
    
    if not docx_files:
        print("没有找到 ATG 文档")
        return
    
    test_file = os.path.join(upload_dir, docx_files[0])
    print(f"测试文件: {docx_files[0]}\n")
    
    # 提取文档
    result = extract_word(test_file)
    print(f"表格数: {len(result.tables)}")
    
    # 查找 Label 273 相关表格
    print("\n=== 查找 Label 273 相关表格 ===")
    
    for i, table in enumerate(result.tables):
        table_str = json.dumps(table, ensure_ascii=False)
        if '273' in table_str or 'Label_273' in table_str:
            print(f"\n--- 表格 {i} ---")
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            print(f"表头: {headers}")
            print(f"行数: {len(rows)}")
            
            # 显示所有行
            for j, row in enumerate(rows):
                cells = row.get('cells', [])
                cells_short = [str(c)[:25] if c else '' for c in cells]
                print(f"  行{j}: {cells_short}")
            
            # 预解析
            preparse = preparse_arinc429_table(table)
            parsed_labels = preparse.get('parsed_labels', [])
            for label in parsed_labels:
                if label.get('label_oct') == '273':
                    print(f"\n  预解析 Label 273:")
                    print(json.dumps(label, ensure_ascii=False, indent=4))
    
    # 查看 Markdown 中 Label 273 的部分
    print("\n=== Markdown 中 Label 273 部分 ===")
    md = convert_to_markdown(result, max_chars=200000)
    
    lines = md.split('\n')
    for i, line in enumerate(lines):
        if '273' in line or 'Label_273' in line:
            start = max(0, i - 3)
            end = min(len(lines), i + 20)
            print('\n'.join(lines[start:end]))
            print("\n---\n")
            break
    
    # 调用 LLM 看返回结果
    print("\n=== 调用 LLM 检查 Label 273 ===")
    
    preparse_results = []
    for table in result.tables:
        preparse = preparse_arinc429_table(table)
        if preparse.get('parsed_labels'):
            preparse_results.append(preparse)
    
    context = build_llm_prompt_context_v2(result, preparse_results, max_chars=100000)
    system_prompt = get_system_prompt('ARINC429')
    
    api_key = os.environ.get('LLM_API_KEY', '')
    if not api_key:
        print("API Key 未配置")
        return
    
    try:
        parsed = _call_llm_api(context, system_prompt)
        labels = parsed.get('labels', [])
        print(f"LLM 返回 {len(labels)} 个 Label")
        
        # 找 Label 273
        found = False
        for label in labels:
            if label.get('label_oct') == '273':
                found = True
                print("\nLabel 273 的 LLM 解析结果:")
                print(json.dumps(label, ensure_ascii=False, indent=2))
                
                bnr = label.get('bnr_fields', [])
                discrete = label.get('discrete_bits', {})
                special = label.get('special_fields', [])
                
                print(f"\n字段统计:")
                print(f"  bnr_fields: {len(bnr)} 个")
                print(f"  discrete_bits: {len(discrete)} 个")
                print(f"  special_fields: {len(special)} 个")
                break
        
        if not found:
            print("❌ LLM 没有返回 Label 273！")
            print("\n返回的所有 Label:")
            for label in labels:
                print(f"  - {label.get('label_oct')}: {label.get('name', '')[:30]}")
            
    except Exception as e:
        print(f"LLM 调用失败: {e}")

if __name__ == '__main__':
    main()
