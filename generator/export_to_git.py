#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出数据库到 Git 仓库
运行此脚本将现有数据库中的设备和协议数据导出到按 ATA 分的 Git 仓库
"""

import os
import sys
import argparse

# 确保可以导入 git_storage 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_storage.db_exporter import export_database_to_git


def main():
    parser = argparse.ArgumentParser(
        description='导出数据库到 Git 仓库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python export_to_git.py              # 执行导出
  python export_to_git.py --dry-run    # 仅分析，不实际写入
        '''
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='仅分析数据库内容，不实际写入 Git 仓库'
    )
    
    args = parser.parse_args()
    
    print()
    print('ARINC429 协议平台 - 数据库导出工具')
    print('=' * 50)
    print()
    
    if args.dry_run:
        print('模式: 仅分析 (dry-run)')
    else:
        print('模式: 实际导出')
        print()
        confirm = input('确认要导出数据库到 Git 仓库吗? (y/N): ')
        if confirm.lower() != 'y':
            print('已取消')
            return
    
    print()
    
    stats = export_database_to_git(dry_run=args.dry_run)
    
    print()
    print('导出统计:')
    print(f'  - ATA 仓库: {stats.get("ata_repos_created", 0)}')
    print(f'  - 设备: {stats.get("devices_exported", 0)}')
    print(f'  - Labels: {stats.get("labels_exported", 0)}')
    print(f'  - 版本记录: {stats.get("versions_exported", 0)}')
    
    errors = stats.get('errors', [])
    if errors:
        print(f'  - 错误: {len(errors)}')


if __name__ == '__main__':
    main()
