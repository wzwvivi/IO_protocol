# -*- coding: utf-8 -*-
"""调试 LLM 输出和转换过程"""
import os
import sys
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_extractors import extract_word, extract_excel, build_llm_prompt_context_v2
from llm_parser import parse_protocol_with_llm, _call_llm_api, get_system_prompt

def main():
    # 找到上传的文件
    upload_dir = os.path.join(os.path.dirname(__file__), 'data', 'uploads')
    if not os.path.exists(upload_dir):
        upload_dir = '/app/data/uploads'
    
    print(f"=== 上传目录: {upload_dir} ===")
    
    files = os.listdir(upload_dir)
    docx_files = [f for f in files if f.endswith('.docx') and not f.startswith('~')]
    
    if not docx_files:
        print("没有找到 .docx 文件")
        return
    
    print(f"找到 {len(docx_files)} 个 docx 文件")
    for f in docx_files[:5]:
        print(f"  - {f}")
    
    # 选择第一个文件测试
    test_file = os.path.join(upload_dir, docx_files[0])
    print(f"\n=== 测试文件: {docx_files[0]} ===\n")
    
    # 1. 提取文档内容
    print("【步骤1】提取文档内容...")
    result = extract_word(test_file)
    print(f"  段落数: {len(result.paragraphs)}")
    print(f"  表格数: {len(result.tables)}")
    
    # 2. 预解析表格
    print("\n【步骤2】预解析表格...")
    from document_extractors import preparse_arinc429_table
    preparse_results = []
    for table in result.tables:
        preparse = preparse_arinc429_table(table)
        if preparse.get('parsed_labels'):
            preparse_results.append(preparse)
    
    total_preparsed = sum(len(p.get('parsed_labels', [])) for p in preparse_results)
    print(f"  预解析出 {total_preparsed} 个 Label")
    
    # 3. 构建 LLM 上下文
    print("\n【步骤3】构建 LLM 上下文...")
    context = build_llm_prompt_context_v2(result, preparse_results, max_chars=100000)
    print(f"  上下文长度: {len(context)} 字符")
    
    # 4. 调用 LLM
    print("\n【步骤4】调用 LLM...")
    system_prompt = get_system_prompt('ARINC429')
    print(f"  System Prompt 长度: {len(system_prompt)} 字符")
    
    api_key = os.environ.get('LLM_API_KEY', '')
    api_base = os.environ.get('LLM_API_BASE_URL', 'https://api.openai.com/v1')
    model = os.environ.get('LLM_MODEL', 'gpt-4o-mini')
    
    print(f"  API: {api_base}")
    print(f"  Model: {model}")
    print(f"  API Key: {'已配置' if api_key else '未配置'}")
    
    if not api_key:
        print("  ⚠️ API Key 未配置，跳过 LLM 调用")
        return
    
    # 直接调用 LLM API 获取原始响应
    print("\n  正在调用 LLM API...")
    try:
        # _call_llm_api 返回解析后的 Dict，不是原始字符串
        parsed = _call_llm_api(context, system_prompt)
        print("  ✅ LLM 调用成功")
    except Exception as e:
        print(f"  ❌ LLM 调用失败: {e}")
        return
    
    print(f"\n【步骤5】LLM 返回的 JSON 结构:")
    print("=" * 60)
    raw_json = json.dumps(parsed, ensure_ascii=False, indent=2)
    print(raw_json[:3000] if len(raw_json) > 3000 else raw_json)
    print("=" * 60)
    
    # 6. 检查解析结果
    print("\n【步骤6】检查 LLM 返回的 Labels...")
    
    try:
        labels = parsed.get('labels', [])
        print(f"  ✅ 解析成功，共 {len(labels)} 个 Label")
        
        # 检查每个 Label 的字段
        print("\n【步骤7】检查 Label 字段填充情况:")
        
        has_bnr = 0
        has_discrete = 0
        has_special = 0
        empty_all = 0
        
        for i, label in enumerate(labels[:10]):  # 只显示前10个
            label_oct = label.get('label_oct', '?')
            name = label.get('name', '')
            bnr = label.get('bnr_fields', [])
            discrete = label.get('discrete_bits', {})
            special = label.get('special_fields', [])
            
            if bnr:
                has_bnr += 1
            if discrete:
                has_discrete += 1
            if special:
                has_special += 1
            if not bnr and not discrete and not special:
                empty_all += 1
            
            print(f"\n  Label {label_oct}: {name[:30] if name else '(无名称)'}")
            print(f"    bnr_fields: {len(bnr)} 个")
            if bnr:
                for b in bnr[:2]:
                    print(f"      - {b.get('name', '?')}: bits={b.get('data_bits')}, sign={b.get('sign_bit')}, res={b.get('resolution')}")
            print(f"    discrete_bits: {len(discrete)} 个")
            if discrete:
                for k, v in list(discrete.items())[:3]:
                    print(f"      - bit {k}: {v[:40] if len(str(v)) > 40 else v}")
            print(f"    special_fields: {len(special)} 个")
            if special:
                for s in special[:2]:
                    print(f"      - {s.get('name', '?')}: bits={s.get('bits')}, values={list(s.get('values', {}).keys())[:3]}")
        
        print(f"\n【统计】共 {len(labels)} 个 Label:")
        print(f"  有 bnr_fields: {has_bnr}")
        print(f"  有 discrete_bits: {has_discrete}")
        print(f"  有 special_fields: {has_special}")
        print(f"  全部为空: {empty_all}")
        
        # 8. 调用完整的解析流程
        print("\n【步骤8】调用完整解析流程 parse_protocol_with_llm...")
        # 收集预解析的 labels
        all_preparsed = []
        for p in preparse_results:
            all_preparsed.extend(p.get('parsed_labels', []))
        full_result, full_errors = parse_protocol_with_llm(context, all_preparsed, 'ARINC429')
        
        final_labels = full_result.get('labels', [])
        
        print(f"  最终 Label 数量: {len(final_labels)}")
        if full_errors:
            print(f"  错误: {full_errors}")
        
        # 比较差异
        print("\n【步骤9】比较 LLM 原始输出 vs 最终结果:")
        
        final_has_bnr = sum(1 for l in final_labels if l.get('bnr_fields'))
        final_has_discrete = sum(1 for l in final_labels if l.get('discrete_bits'))
        final_has_special = sum(1 for l in final_labels if l.get('special_fields'))
        final_empty = sum(1 for l in final_labels if not l.get('bnr_fields') and not l.get('discrete_bits') and not l.get('special_fields'))
        
        print(f"  LLM原始 → 最终结果")
        print(f"  有 bnr_fields:     {has_bnr} → {final_has_bnr}")
        print(f"  有 discrete_bits:  {has_discrete} → {final_has_discrete}")
        print(f"  有 special_fields: {has_special} → {final_has_special}")
        print(f"  全部为空:          {empty_all} → {final_empty}")
        
        if has_bnr != final_has_bnr or has_discrete != final_has_discrete or has_special != final_has_special:
            print("\n  ⚠️ 数据在转换过程中有丢失！")
        else:
            print("\n  ✅ 数据转换无丢失")
        
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")

if __name__ == '__main__':
    main()
