#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建完整数据库
在打包 Docker 镜像前运行此脚本，将完整的设备树和版本信息导入数据库
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_db_path, get_db_connection
from device_manager import import_device_tree_from_directory, save_device_tree_to_db
from init_users import init_default_admin
import json

# 数据协议目录
DATA_PROTOCOL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '数据协议')


def build_full_database(force_reset=False):
    """构建包含完整设备树的数据库
    
    Args:
        force_reset: 如果为 True，强制删除现有数据库重新创建
    """
    
    print('=' * 60)
    print('构建完整数据库')
    print('=' * 60)
    print()
    
    # 1. 确保 data 目录存在
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    db_path = get_db_path()
    
    # 2. 检查是否已有数据库
    if os.path.exists(db_path):
        if force_reset:
            print(f'⚠ 强制重置：删除现有数据库: {db_path}')
            os.remove(db_path)
        else:
            # 检查数据库是否有数据
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT COUNT(*) FROM devices')
                device_count = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM labels')
                label_count = cursor.fetchone()[0]
                conn.close()
                
                if device_count > 0 or label_count > 0:
                    print(f'✓ 数据库已存在且有数据 ({device_count} 个设备, {label_count} 个 Labels)')
                    print('  如需重置，请使用: python build_full_db.py --reset')
                    print()
                    verify_database()
                    return True
            except:
                conn.close()
                # 表不存在，需要初始化
    
    # 3. 初始化数据库结构
    print('1. 初始化数据库表结构...')
    init_database()
    print(f'   数据库路径: {db_path}')
    
    # 4. 创建管理员账户
    print('2. 创建管理员账户...')
    init_default_admin()
    print('   ✓ 管理员: admin / admin123')
    
    # 5. 导入完整设备树
    print('3. 导入完整设备树...')
    
    if not os.path.exists(DATA_PROTOCOL_DIR):
        print(f'   ❌ 数据协议目录不存在: {DATA_PROTOCOL_DIR}')
        return False
    
    device_tree = import_device_tree_from_directory(DATA_PROTOCOL_DIR)
    
    if not device_tree:
        print('   ❌ 未找到任何设备')
        return False
    
    print(f'   找到 {len(device_tree)} 个顶级系统')
    
    # 6. 保存到数据库
    print('4. 保存设备树到数据库...')
    save_device_tree_to_db(device_tree)
    print('   ✓ 保存成功')
    
    # 7. 导入示例 Labels（32-3 转弯控制单元）
    print('5. 导入示例 Labels...')
    load_example_labels()
    
    # 8. 验证
    print('6. 验证数据库...')
    verify_database()
    
    print()
    print('=' * 60)
    print('✓ 完整数据库构建完成！')
    print()
    print(f'数据库文件: {db_path}')
    print('该数据库将被打包进 Docker 镜像')
    print('=' * 60)
    
    return True


def load_example_labels():
    """加载示例 Label 配置到转弯控制单元的 V5.0 版本"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    example_path = os.path.join(base_dir, 'example_protocol_config.json')
    
    if not os.path.exists(example_path):
        print('   ⚠ 示例配置文件不存在，跳过 Label 导入')
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 获取转弯控制单元的 ID
        cursor.execute('SELECT id FROM devices WHERE device_id = ?', ('ata32_32_3',))
        row = cursor.fetchone()
        if not row:
            print('   ⚠ 转弯控制单元不存在，跳过 Label 导入')
            return
        
        device_pk = row[0]
        
        # 获取 V5.0 协议版本的 ID
        cursor.execute('''
            SELECT id, version_name FROM device_protocol_versions 
            WHERE device_id = ? AND version_name LIKE '%V5.0%'
        ''', (device_pk,))
        ver_row = cursor.fetchone()
        
        if not ver_row:
            # 如果没有 V5.0，尝试获取第一个版本
            cursor.execute('''
                SELECT id, version_name FROM device_protocol_versions 
                WHERE device_id = ? ORDER BY id LIMIT 1
            ''', (device_pk,))
            ver_row = cursor.fetchone()
        
        protocol_version_id = ver_row[0] if ver_row else None
        version_name = ver_row[1] if ver_row else '未知版本'
        
        # 检查是否已有 labels
        if protocol_version_id:
            cursor.execute('SELECT COUNT(*) FROM labels WHERE device_id = ? AND protocol_version_id = ?', 
                          (device_pk, protocol_version_id))
        else:
            cursor.execute('SELECT COUNT(*) FROM labels WHERE device_id = ?', (device_pk,))
        
        if cursor.fetchone()[0] > 0:
            print('   ✓ Labels 已存在，跳过')
            return
        
        # 加载示例配置
        with open(example_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        labels = config.get('labels', [])
        
        for label in labels:
            cursor.execute('''
                INSERT INTO labels (device_id, protocol_version_id, label_oct, name, direction, sources, data_type,
                                   unit, range_desc, resolution, reserved_bits, notes,
                                   discrete_bits, special_fields, bnr_fields, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ''', (
                device_pk,
                protocol_version_id,
                label.get('label_oct', ''),
                label.get('name', ''),
                label.get('direction', ''),
                json.dumps(label.get('sources', []), ensure_ascii=False),
                label.get('data_type', ''),
                label.get('unit', ''),
                label.get('range', ''),
                label.get('resolution'),
                label.get('reserved_bits', ''),
                label.get('notes', ''),
                json.dumps(label.get('discrete_bits', {}), ensure_ascii=False),
                json.dumps(label.get('special_fields', []), ensure_ascii=False),
                json.dumps(label.get('bnr_fields', []), ensure_ascii=False),
            ))
        
        # 更新设备版本和当前版本名
        cursor.execute('''
            UPDATE devices SET device_version = ?, current_version_name = ? WHERE id = ?
        ''', (config.get('protocol_meta', {}).get('version', 'V5.0'), version_name, device_pk))
        
        conn.commit()
        print(f'   ✓ 已导入 {len(labels)} 个示例 Labels 到 32-3-转弯控制单元 ({version_name})')


def verify_database():
    """验证数据库内容"""
    import sqlite3
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 统计
    cursor.execute("SELECT COUNT(*) FROM devices")
    device_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM devices WHERE is_device = 1")
    is_device_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM device_protocol_versions")
    version_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM labels")
    label_count = cursor.fetchone()[0]
    
    print(f'   - 总节点数: {device_count}')
    print(f'   - 设备节点数: {is_device_count}')
    print(f'   - 协议版本数: {version_count}')
    print(f'   - Labels 数: {label_count}')
    
    # 显示有版本的设备
    cursor.execute("""
        SELECT d.name, COUNT(dpv.id) as ver_count
        FROM devices d
        LEFT JOIN device_protocol_versions dpv ON d.id = dpv.device_id
        WHERE d.is_device = 1
        GROUP BY d.id
        HAVING ver_count > 0
        ORDER BY d.name
    """)
    devices_with_versions = cursor.fetchall()
    
    if devices_with_versions:
        print(f'   - 有协议版本的设备:')
        for name, count in devices_with_versions:
            print(f'      {name}: {count} 个版本')
    
    conn.close()


if __name__ == '__main__':
    import sys
    
    force_reset = '--reset' in sys.argv or '-f' in sys.argv
    
    if force_reset:
        confirm = input('⚠ 警告：这将删除所有现有数据！确定要继续吗？(y/N): ')
        if confirm.lower() != 'y':
            print('已取消')
            sys.exit(0)
    
    build_full_database(force_reset=force_reset)
