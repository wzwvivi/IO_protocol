# -*- coding: utf-8 -*-
"""导出文档转换后的 Markdown 内容"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_extractors import extract_document, convert_to_markdown

def main():
    # 查找上传的文件
    uploads_dir = os.environ.get('UPLOADS_DIR', '/app/data/uploads')
    if not os.path.exists(uploads_dir):
        uploads_dir = 'data/uploads'
    
    if not os.path.exists(uploads_dir):
        print(f"上传目录不存在: {uploads_dir}")
        return
    
    files = os.listdir(uploads_dir)
    atg_files = [f for f in files if 'ATG' in f and f.endswith('.docx')]
    
    if not atg_files:
        print("没有找到 ATG 文件")
        print(f"可用文件: {files[:10]}")
        return
    
    test_file = os.path.join(uploads_dir, atg_files[0])
    print(f"处理文件: {test_file}")
    
    # 提取文档
    result = extract_document(test_file)
    print(f"段落数: {len(result.paragraphs)}")
    print(f"表格数: {len(result.tables)}")
    
    # 转换为 Markdown
    md_content = convert_to_markdown(result, max_chars=200000)
    
    # 保存到文件
    output_path = '/app/data/extracted_content.md'
    if not os.path.exists('/app/data'):
        output_path = 'data/extracted_content.md'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"\nMarkdown 已保存到: {output_path}")
    print(f"内容长度: {len(md_content)} 字符")
    
    # 显示前 5000 字符
    print("\n" + "=" * 80)
    print("Markdown 内容预览（前 5000 字符）:")
    print("=" * 80)
    print(md_content[:5000])
    
    if len(md_content) > 5000:
        print(f"\n... 还有 {len(md_content) - 5000} 字符")

if __name__ == '__main__':
    main()
