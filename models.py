# -*- coding: utf-8 -*-
"""
用户管理模块 - 数据模型和认证功能
使用 SQLite 数据库存储
"""

import os
import hashlib
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, request, jsonify

from database import (
    init_database, db_get_user, db_create_user, db_update_user,
    db_delete_user, db_list_users, db_count_admins
)


def ensure_user_db():
    """确保数据库已初始化，并存在默认管理员"""
    init_database()
    
    # 检查是否有管理员
    admin = db_get_user('admin')
    if not admin:
        # 创建默认管理员账户
        success, msg = db_create_user(
            username='admin',
            password_hash=hash_password('admin123'),
            display_name='管理员',
            email='admin@example.com',
            role='admin'
        )
        if success:
            print('已创建默认管理员账户: admin / admin123')
    
    return True


def hash_password(password):
    """密码哈希（使用 SHA-256 + salt）"""
    salt = 'arinc429_platform_salt_2024'
    return hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()


def verify_password(password, password_hash):
    """验证密码"""
    return hash_password(password) == password_hash


def create_user(username, password, display_name='', email='', role='user'):
    """创建新用户
    
    Args:
        username: 用户名（唯一标识）
        password: 明文密码
        display_name: 显示名称
        email: 邮箱
        role: 角色 ('admin' 或 'user')
    
    Returns:
        (success, message)
    """
    # 检查用户名是否已存在
    existing = db_get_user(username)
    if existing:
        return False, '用户名已存在'
    
    # 验证用户名格式
    if len(username) < 3 or len(username) > 20:
        return False, '用户名长度需在3-20个字符之间'
    
    if not username.replace('_', '').isalnum():
        return False, '用户名只能包含字母、数字和下划线'
    
    # 验证密码强度
    if len(password) < 6:
        return False, '密码长度至少6位'
    
    # 创建用户
    return db_create_user(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        email=email,
        role=role
    )


def authenticate_user(username, password):
    """验证用户登录
    
    Returns:
        (success, user_data or error_message)
    """
    user = db_get_user(username)
    
    if not user:
        return False, '用户名不存在'
    
    if not user.get('is_active', True):
        return False, '账户已被禁用'
    
    if not verify_password(password, user['password_hash']):
        return False, '密码错误'
    
    # 更新最后登录时间
    db_update_user(username, last_login=datetime.now().isoformat())
    
    return True, user


def get_user(username):
    """获取用户信息"""
    return db_get_user(username)


def update_user(username, **kwargs):
    """更新用户信息
    
    可更新字段: display_name, email, is_active, role
    """
    user = db_get_user(username)
    if not user:
        return False, '用户不存在'
    
    # 转换 is_active 为整数
    if 'is_active' in kwargs:
        kwargs['is_active'] = 1 if kwargs['is_active'] else 0
    
    return db_update_user(username, **kwargs)


def change_password(username, old_password, new_password):
    """修改密码"""
    user = db_get_user(username)
    
    if not user:
        return False, '用户不存在'
    
    if not verify_password(old_password, user['password_hash']):
        return False, '原密码错误'
    
    if len(new_password) < 6:
        return False, '新密码长度至少6位'
    
    return db_update_user(username, password_hash=hash_password(new_password))


def reset_password(username, new_password):
    """重置密码（管理员操作）"""
    user = db_get_user(username)
    
    if not user:
        return False, '用户不存在'
    
    if len(new_password) < 6:
        return False, '新密码长度至少6位'
    
    return db_update_user(username, password_hash=hash_password(new_password))


def delete_user(username):
    """删除用户"""
    user = db_get_user(username)
    
    if not user:
        return False, '用户不存在'
    
    if user['role'] == 'admin':
        # 检查是否是最后一个管理员
        admin_count = db_count_admins()
        if admin_count <= 1:
            return False, '不能删除最后一个管理员账户'
    
    return db_delete_user(username)


def list_users():
    """列出所有用户（不含密码哈希）"""
    users = db_list_users()
    # 转换 is_active 为布尔值
    for user in users:
        user['is_active'] = bool(user.get('is_active', 1))
    return users


# ============================================================
# Flask 装饰器和辅助函数
# ============================================================

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # 判断是 API 请求还是页面请求
            if request.path.startswith('/api/'):
                return jsonify({'error': '请先登录', 'code': 401}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': '请先登录', 'code': 401}), 401
            return redirect(url_for('login'))
        
        if session['user'].get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': '需要管理员权限', 'code': 403}), 403
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """获取当前登录用户"""
    return session.get('user')


def is_logged_in():
    """检查是否已登录"""
    return 'user' in session


def is_admin():
    """检查当前用户是否为管理员"""
    user = get_current_user()
    return user and user.get('role') == 'admin'
