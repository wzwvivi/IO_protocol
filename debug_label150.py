# -*- coding: utf-8 -*-
"""调试 Label 150 的解析 - 测试 LLM 输出"""
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
    
    # 预解析
    preparse_results = []
    for table in result.tables:
        preparse = preparse_arinc429_table(table)
        if preparse.get('parsed_labels'):
            preparse_results.append(preparse)
    
    # 构建上下文
    context = build_llm_prompt_context_v2(result, preparse_results, max_chars=100000)
    print(f"上下文长度: {len(context)} 字符")
    
    # 调用 LLM
    print("\n=== 调用 LLM ===")
    system_prompt = get_system_prompt('ARINC429')
    print(f"System Prompt 长度: {len(system_prompt)} 字符")
    
    api_key = os.environ.get('LLM_API_KEY', '')
    if not api_key:
        print("API Key 未配置")
        return
    
    try:
        parsed = _call_llm_api(context, system_prompt)
        labels = parsed.get('labels', [])
        print(f"LLM 返回 {len(labels)} 个 Label")
        
        # 找 Label 150
        print("\n=== Label 150 的 LLM 解析结果 ===")
        found = False
        for label in labels:
            if label.get('label_oct') == '150':
                found = True
                print(json.dumps(label, ensure_ascii=False, indent=2))
                
                # 检查字段
                bnr = label.get('bnr_fields', [])
                discrete = label.get('discrete_bits', {})
                special = label.get('special_fields', [])
                
                print(f"\n字段统计:")
                print(f"  bnr_fields: {len(bnr)} 个")
                for b in bnr:
                    print(f"    - {b.get('name')}: bits={b.get('data_bits')}")
                print(f"  discrete_bits: {len(discrete)} 个")
                for k, v in discrete.items():
                    print(f"    - bit {k}: {v}")
                print(f"  special_fields: {len(special)} 个")
                for s in special:
                    print(f"    - {s.get('name')}: bits={s.get('bits')}")
                break
        
        if not found:
            print("❌ LLM 没有返回 Label 150！")
            print("\n返回的 Label 列表:")
            for label in labels[:10]:
                print(f"  - {label.get('label_oct')}: {label.get('name', '')[:30]}")
            
    except Exception as e:
        print(f"LLM 调用失败: {e}")

if __name__ == '__main__':
    main()
