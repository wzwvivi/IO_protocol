# -*- coding: utf-8 -*-
"""将 PDF 转换为图片"""
import os
import sys

try:
    # 尝试使用 PyMuPDF (fitz)
    import fitz
    USE_FITZ = True
except ImportError:
    USE_FITZ = False
    try:
        # 尝试使用 pdf2image
        from pdf2image import convert_from_path
        USE_PDF2IMAGE = True
    except ImportError:
        USE_PDF2IMAGE = False
        print("错误: 需要安装 PyMuPDF 或 pdf2image")
        print("请运行: pip install PyMuPDF")
        print("或: pip install pdf2image")
        sys.exit(1)

from PIL import Image

def convert_pdf_to_images_fitz(pdf_path, output_dir, dpi=200):
    """使用 PyMuPDF 转换 PDF"""
    print(f"使用 PyMuPDF 转换: {pdf_path}")
    
    # 打开 PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    print(f"总页数: {total_pages}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 转换每一页
    for page_num in range(total_pages):
        page = doc[page_num]
        
        # 设置缩放比例以提高分辨率
        zoom = dpi / 72  # 72 是默认 DPI
        mat = fitz.Matrix(zoom, zoom)
        
        # 渲染页面为图片
        pix = page.get_pixmap(matrix=mat)
        
        # 保存图片
        output_path = os.path.join(output_dir, f"page_{page_num + 1:03d}.png")
        pix.save(output_path)
        
        print(f"  已转换: 第 {page_num + 1}/{total_pages} 页 -> {output_path}")
    
    doc.close()
    print(f"\n✓ 转换完成！共 {total_pages} 页")
    print(f"  输出目录: {output_dir}")

def convert_pdf_to_images_pdf2image(pdf_path, output_dir, dpi=200):
    """使用 pdf2image 转换 PDF"""
    print(f"使用 pdf2image 转换: {pdf_path}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 转换 PDF
    images = convert_from_path(pdf_path, dpi=dpi)
    total_pages = len(images)
    
    print(f"总页数: {total_pages}")
    
    # 保存每一页
    for i, image in enumerate(images):
        output_path = os.path.join(output_dir, f"page_{i + 1:03d}.png")
        image.save(output_path, 'PNG')
        print(f"  已转换: 第 {i + 1}/{total_pages} 页 -> {output_path}")
    
    print(f"\n✓ 转换完成！共 {total_pages} 页")
    print(f"  输出目录: {output_dir}")

def main():
    # PDF 文件路径
    pdf_path = r"C:\Users\wangz\Desktop\协议\方案二.pdf"
    
    # 输出目录
    output_dir = r"C:\Users\wangz\Desktop\协议\方案二_images"
    
    # 检查 PDF 是否存在
    if not os.path.exists(pdf_path):
        print(f"错误: PDF 文件不存在: {pdf_path}")
        sys.exit(1)
    
    # 转换
    if USE_FITZ:
        convert_pdf_to_images_fitz(pdf_path, output_dir, dpi=200)
    elif USE_PDF2IMAGE:
        convert_pdf_to_images_pdf2image(pdf_path, output_dir, dpi=200)
    else:
        print("错误: 没有可用的 PDF 转换库")
        sys.exit(1)

if __name__ == '__main__':
    main()
