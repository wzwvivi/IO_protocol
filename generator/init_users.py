# -*- coding: utf-8 -*-
"""
用户数据库初始化脚本
运行此脚本可以:
1. 初始化数据库
2. 创建默认管理员账户
3. 重置管理员密码
4. 创建测试用户
5. 迁移旧数据
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, migrate_from_json, db_list_users, db_count_admins
from models import (
    ensure_user_db, create_user, reset_password, list_users, hash_password
)


def init_default_admin():
    """初始化默认管理员账户"""
    init_database()
    ensure_user_db()
    print('✓ 数据库初始化完成')


def reset_admin_password(new_password='admin123'):
    """重置管理员密码"""
    success, msg = reset_password('admin', new_password)
    if success:
        print(f'✓ 管理员密码已重置为: {new_password}')
    else:
        print(f'✗ 重置失败: {msg}')


def create_test_users():
    """创建测试用户"""
    test_users = [
        ('user1', 'user123', '测试用户1', 'user1@test.com', 'user'),
        ('user2', 'user123', '测试用户2', 'user2@test.com', 'user'),
        ('engineer', 'eng123', '工程师', 'engineer@test.com', 'user'),
    ]
    
    for username, password, display_name, email, role in test_users:
        success, msg = create_user(username, password, display_name, email, role)
        if success:
            print(f'✓ 已创建用户: {username} / {password}')
        else:
            print(f'ℹ 用户 {username}: {msg}')


def show_all_users():
    """显示所有用户"""
    users = list_users()
    print('\n当前用户列表:')
    print('-' * 60)
    print(f'{"用户名":<15} {"显示名称":<15} {"角色":<10} {"状态":<8}')
    print('-' * 60)
    for u in users:
        status = '正常' if u.get('is_active', True) else '禁用'
        role = '管理员' if u['role'] == 'admin' else '用户'
        print(f'{u["username"]:<15} {u["display_name"]:<15} {role:<10} {status:<8}')
    print('-' * 60)
    print(f'共 {len(users)} 个用户\n')


def migrate_data():
    """从 JSON 迁移数据到 SQLite"""
    init_database()
    migrate_from_json()


def main():
    print('=' * 60)
    print('接口代码生成平台 - 用户初始化')
    print('=' * 60)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == 'init':
            init_default_admin()
        elif cmd == 'reset':
            new_pwd = sys.argv[2] if len(sys.argv) > 2 else 'admin123'
            reset_admin_password(new_pwd)
        elif cmd == 'test':
            create_test_users()
        elif cmd == 'list':
            show_all_users()
        elif cmd == 'migrate':
            migrate_data()
        elif cmd == 'all':
            init_default_admin()
            create_test_users()
            show_all_users()
        else:
            print('未知命令')
            print_usage()
    else:
        print_usage()


def print_usage():
    print('''
用法:
  python init_users.py init          初始化数据库和默认管理员账户
  python init_users.py reset [pwd]   重置管理员密码 (默认: admin123)
  python init_users.py test          创建测试用户
  python init_users.py list          显示所有用户
  python init_users.py migrate       从 JSON 迁移数据到 SQLite
  python init_users.py all           执行所有初始化操作
''')


if __name__ == '__main__':
    main()
