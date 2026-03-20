# -*- coding: utf-8 -*-
"""
SQLite 数据库模块
负责数据库连接、表结构、数据迁移
"""

import os
import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

# 数据库文件路径
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'arinc429.db')


def get_db_path():
    """获取数据库路径"""
    return DB_PATH


@contextmanager
def get_db_connection():
    """获取数据库连接（上下文管理器）"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 返回字典形式的行
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """初始化数据库表结构"""
    os.makedirs(DB_DIR, exist_ok=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                display_name TEXT,
                email TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                last_login TEXT
            )
        ''')
        
        # 设备表（支持层级结构）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                parent_id INTEGER,
                is_device INTEGER DEFAULT 0,
                device_version TEXT DEFAULT 'V1.0',
                current_version_name TEXT,
                description TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (parent_id) REFERENCES devices(id) ON DELETE CASCADE
            )
        ''')
        
        # 设备协议版本表（从目录导入的版本）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_protocol_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                version_name TEXT NOT NULL,
                version TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
                UNIQUE(device_id, version_name)
            )
        ''')
        
        # Label 定义表（每个 Label 关联到设备的特定协议版本）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                protocol_version_id INTEGER,
                label_oct TEXT NOT NULL,
                name TEXT NOT NULL,
                direction TEXT,
                sources TEXT,
                data_type TEXT,
                unit TEXT,
                range_desc TEXT,
                resolution REAL,
                reserved_bits TEXT,
                notes TEXT,
                discrete_bits TEXT,
                special_fields TEXT,
                bnr_fields TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
                FOREIGN KEY (protocol_version_id) REFERENCES device_protocol_versions(id) ON DELETE CASCADE,
                UNIQUE(device_id, protocol_version_id, label_oct)
            )
        ''')
        
        # 版本历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS version_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                version TEXT NOT NULL,
                updated_at TEXT,
                updated_by TEXT,
                change_summary TEXT,
                diff_summary TEXT,
                label_snapshot TEXT,
                label_count INTEGER,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            )
        ''')
        
        # 用户配置表（协议元信息等）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                protocol_meta TEXT,
                settings TEXT,
                updated_at TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_parent ON devices(parent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_labels_device ON labels(device_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_labels_oct ON labels(label_oct)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_version_history_device ON version_history(device_id)')
        
        conn.commit()
        print(f'数据库初始化完成: {DB_PATH}')


def row_to_dict(row):
    """将 sqlite3.Row 转换为字典"""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """将多行结果转换为字典列表"""
    return [dict(row) for row in rows]


# ============================================================
# 用户相关操作
# ============================================================

def db_get_user(username):
    """获取用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username,))
        row = cursor.fetchone()
        return row_to_dict(row)


def db_get_user_by_id(user_id):
    """根据ID获取用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return row_to_dict(row)


def db_create_user(username, password_hash, display_name='', email='', role='user'):
    """创建用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash, display_name, email, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            ''', (username, password_hash, display_name or username, email, role, datetime.now().isoformat()))
            conn.commit()
            return True, '用户创建成功'
        except sqlite3.IntegrityError:
            return False, '用户名已存在'


def db_update_user(username, **kwargs):
    """更新用户信息"""
    allowed_fields = ['display_name', 'email', 'is_active', 'role', 'password_hash', 'last_login']
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in kwargs:
            updates.append(f'{field} = ?')
            values.append(kwargs[field])
    
    if not updates:
        return False, '没有要更新的字段'
    
    values.append(username)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE users SET {', '.join(updates)} WHERE LOWER(username) = LOWER(?)
        ''', values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return False, '用户不存在'
        return True, '用户信息已更新'


def db_delete_user(username):
    """删除用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE LOWER(username) = LOWER(?)', (username,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return False, '用户不存在'
        return True, '用户已删除'


def db_list_users():
    """列出所有用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, role, display_name, email, is_active, created_at, last_login 
            FROM users ORDER BY created_at
        ''')
        return rows_to_list(cursor.fetchall())


def db_count_admins():
    """统计管理员数量"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        return cursor.fetchone()[0]


# ============================================================
# 设备相关操作
# ============================================================

def db_get_device(device_id):
    """根据 device_id 获取设备"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE device_id = ?', (device_id,))
        return row_to_dict(cursor.fetchone())


def db_get_device_by_pk(pk):
    """根据主键获取设备"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE id = ?', (pk,))
        return row_to_dict(cursor.fetchone())


def db_create_device(device_id, name, parent_id=None, is_device=False, device_version='V1.0', 
                     current_version_name='', description=''):
    """创建设备"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute('''
                INSERT INTO devices (device_id, name, parent_id, is_device, device_version, 
                                    current_version_name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (device_id, name, parent_id, 1 if is_device else 0, device_version,
                  current_version_name, description, now, now))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def db_update_device(device_id, **kwargs):
    """更新设备"""
    allowed_fields = ['name', 'device_version', 'current_version_name', 'description']
    updates = ['updated_at = ?']
    values = [datetime.now().isoformat()]
    
    for field in allowed_fields:
        if field in kwargs:
            updates.append(f'{field} = ?')
            values.append(kwargs[field])
    
    values.append(device_id)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE devices SET {', '.join(updates)} WHERE device_id = ?
        ''', values)
        conn.commit()
        return cursor.rowcount > 0


def db_delete_device(device_id):
    """删除设备及其关联的 labels、版本历史和协议版本"""
    # 先获取设备的数据库主键
    device = db_get_device(device_id)
    if not device:
        return False
    
    device_pk = device['id']
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 删除关联的 labels
        cursor.execute('DELETE FROM labels WHERE device_id = ?', (device_pk,))
        
        # 删除关联的版本历史
        cursor.execute('DELETE FROM version_history WHERE device_id = ?', (device_pk,))
        
        # 删除关联的协议版本
        cursor.execute('DELETE FROM device_protocol_versions WHERE device_id = ?', (device_pk,))
        
        # 删除设备本身
        cursor.execute('DELETE FROM devices WHERE id = ?', (device_pk,))
        
        conn.commit()
        return cursor.rowcount > 0


def db_get_device_tree():
    """获取完整设备树"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices ORDER BY id')
        devices = rows_to_list(cursor.fetchall())
        
        # 构建树结构
        device_map = {d['id']: d for d in devices}
        root_nodes = []
        
        for device in devices:
            device['children'] = []
            # 获取协议版本
            cursor.execute('SELECT * FROM device_protocol_versions WHERE device_id = ?', (device['id'],))
            versions = rows_to_list(cursor.fetchall())
            if versions:
                device['versions'] = [{'name': v['version_name'], 'version': v['version'], 'labels': []} for v in versions]
            
            if device['parent_id'] is None:
                root_nodes.append(device)
            else:
                parent = device_map.get(device['parent_id'])
                if parent:
                    parent['children'].append(device)
        
        return root_nodes


def db_get_children_devices(parent_id):
    """获取子设备列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if parent_id is None:
            cursor.execute('SELECT * FROM devices WHERE parent_id IS NULL ORDER BY name')
        else:
            cursor.execute('SELECT * FROM devices WHERE parent_id = ? ORDER BY name', (parent_id,))
        return rows_to_list(cursor.fetchall())


# ============================================================
# Label 相关操作
# ============================================================

def db_get_labels(device_id, protocol_version_id=None):
    """获取设备的 Labels
    
    Args:
        device_id: 设备 ID
        protocol_version_id: 协议版本 ID，如果为 None 则获取设备当前版本的 Labels
    """
    device = db_get_device(device_id)
    if not device:
        return []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if protocol_version_id is not None:
            # 获取指定协议版本的 Labels
            cursor.execute('''
                SELECT * FROM labels 
                WHERE device_id = ? AND protocol_version_id = ? 
                ORDER BY label_oct
            ''', (device['id'], protocol_version_id))
        else:
            # 获取设备当前版本的 Labels（protocol_version_id 为 NULL 或当前版本）
            # 先尝试获取当前版本名对应的版本ID
            current_version_name = device.get('current_version_name', '')
            if current_version_name:
                cursor.execute('''
                    SELECT id FROM device_protocol_versions 
                    WHERE device_id = ? AND version_name = ?
                ''', (device['id'], current_version_name))
                ver_row = cursor.fetchone()
                if ver_row:
                    cursor.execute('''
                        SELECT * FROM labels 
                        WHERE device_id = ? AND protocol_version_id = ? 
                        ORDER BY label_oct
                    ''', (device['id'], ver_row[0]))
                else:
                    # 版本不存在，获取没有版本关联的 Labels（兼容旧数据）
                    cursor.execute('''
                        SELECT * FROM labels 
                        WHERE device_id = ? AND protocol_version_id IS NULL 
                        ORDER BY label_oct
                    ''', (device['id'],))
            else:
                # 没有当前版本名，获取所有没有版本关联的 Labels
                cursor.execute('''
                    SELECT * FROM labels 
                    WHERE device_id = ? AND protocol_version_id IS NULL 
                    ORDER BY label_oct
                ''', (device['id'],))
        
        rows = rows_to_list(cursor.fetchall())
        
        # 解析 JSON 字段
        labels = []
        for row in rows:
            label = {
                'label_oct': row['label_oct'],
                'name': row['name'],
                'direction': row['direction'] or '',
                'sources': json.loads(row['sources']) if row['sources'] else [],
                'data_type': row['data_type'] or '',
                'unit': row['unit'] or '',
                'range': row['range_desc'] or '',
                'resolution': row['resolution'],
                'reserved_bits': row['reserved_bits'] or '',
                'notes': row['notes'] or '',
                'discrete_bits': json.loads(row['discrete_bits']) if row['discrete_bits'] else {},
                'special_fields': json.loads(row['special_fields']) if row['special_fields'] else [],
                'bnr_fields': json.loads(row['bnr_fields']) if row['bnr_fields'] else [],
            }
            labels.append(label)
        
        return labels


def db_save_labels(device_id, labels, protocol_version_id=None):
    """保存设备的 Labels（替换指定版本的所有 Labels）
    
    Args:
        device_id: 设备 ID
        labels: Labels 列表
        protocol_version_id: 协议版本 ID，如果为 None 则保存到当前版本
    """
    device = db_get_device(device_id)
    if not device:
        return False
    
    device_pk = device['id']
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 如果没有指定版本，尝试获取当前版本的ID
        actual_version_id = protocol_version_id
        if actual_version_id is None:
            current_version_name = device.get('current_version_name', '')
            if current_version_name:
                cursor.execute('''
                    SELECT id FROM device_protocol_versions 
                    WHERE device_id = ? AND version_name = ?
                ''', (device_pk, current_version_name))
                ver_row = cursor.fetchone()
                if ver_row:
                    actual_version_id = ver_row[0]
        
        # 删除该版本的现有 labels
        if actual_version_id is not None:
            cursor.execute('DELETE FROM labels WHERE device_id = ? AND protocol_version_id = ?', 
                          (device_pk, actual_version_id))
        else:
            cursor.execute('DELETE FROM labels WHERE device_id = ? AND protocol_version_id IS NULL', 
                          (device_pk,))
        
        # 插入新 labels
        for label in labels:
            cursor.execute('''
                INSERT INTO labels (device_id, protocol_version_id, label_oct, name, direction, sources, data_type,
                                   unit, range_desc, resolution, reserved_bits, notes,
                                   discrete_bits, special_fields, bnr_fields, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_pk,
                actual_version_id,
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
                now, now
            ))
        
        conn.commit()
        return True


def db_get_label(device_id, label_oct):
    """获取单个 Label"""
    device = db_get_device(device_id)
    if not device:
        return None
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM labels WHERE device_id = ? AND label_oct = ?', 
                      (device['id'], label_oct))
        row = cursor.fetchone()
        if not row:
            return None
        
        row = dict(row)
        return {
            'label_oct': row['label_oct'],
            'name': row['name'],
            'direction': row['direction'] or '',
            'sources': json.loads(row['sources']) if row['sources'] else [],
            'data_type': row['data_type'] or '',
            'discrete_bits': json.loads(row['discrete_bits']) if row['discrete_bits'] else {},
            'special_fields': json.loads(row['special_fields']) if row['special_fields'] else [],
            'bnr_fields': json.loads(row['bnr_fields']) if row['bnr_fields'] else [],
            'notes': row['notes'] or '',
        }


# ============================================================
# 版本历史相关操作
# ============================================================

def db_add_version_history(device_id, version, updated_by, change_summary, diff_summary, label_snapshot):
    """添加版本历史记录"""
    device = db_get_device(device_id)
    if not device:
        return False
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO version_history (device_id, version, updated_at, updated_by, 
                                        change_summary, diff_summary, label_snapshot, label_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device['id'],
            version,
            datetime.now().isoformat(),
            updated_by,
            change_summary,
            json.dumps(diff_summary, ensure_ascii=False),
            json.dumps(label_snapshot, ensure_ascii=False),
            len(label_snapshot)
        ))
        conn.commit()
        return True


def db_get_version_history(device_id, limit=20):
    """获取版本历史"""
    device = db_get_device(device_id)
    if not device:
        return []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM version_history WHERE device_id = ? 
            ORDER BY updated_at DESC LIMIT ?
        ''', (device['id'], limit))
        rows = rows_to_list(cursor.fetchall())
        
        history = []
        for row in rows:
            history.append({
                'version': row['version'],
                'updated_at': row['updated_at'],
                'updated_by': row['updated_by'],
                'change_summary': row['change_summary'],
                'diff_summary': json.loads(row['diff_summary']) if row['diff_summary'] else {},
                'label_snapshot': json.loads(row['label_snapshot']) if row['label_snapshot'] else [],
                'label_count': row['label_count']
            })
        
        return history


def db_get_version_snapshot(device_id, version):
    """获取特定版本的 labels 快照"""
    device = db_get_device(device_id)
    if not device:
        return None
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT label_snapshot FROM version_history 
            WHERE device_id = ? AND version = ?
        ''', (device['id'], version))
        row = cursor.fetchone()
        
        if row and row['label_snapshot']:
            return json.loads(row['label_snapshot'])
        return None


# ============================================================
# 用户配置相关操作
# ============================================================

def db_get_user_config(username):
    """获取用户配置"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_configs WHERE username = ?', (username,))
        row = cursor.fetchone()
        
        if not row:
            return {'protocol_meta': {'name': '', 'version': '', 'description': ''}, 'settings': {}}
        
        row = dict(row)
        return {
            'protocol_meta': json.loads(row['protocol_meta']) if row['protocol_meta'] else {},
            'settings': json.loads(row['settings']) if row['settings'] else {}
        }


def db_save_user_config(username, protocol_meta=None, settings=None):
    """保存用户配置"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 检查是否存在
        cursor.execute('SELECT id FROM user_configs WHERE username = ?', (username,))
        exists = cursor.fetchone()
        
        now = datetime.now().isoformat()
        
        if exists:
            updates = ['updated_at = ?']
            values = [now]
            
            if protocol_meta is not None:
                updates.append('protocol_meta = ?')
                values.append(json.dumps(protocol_meta, ensure_ascii=False))
            if settings is not None:
                updates.append('settings = ?')
                values.append(json.dumps(settings, ensure_ascii=False))
            
            values.append(username)
            cursor.execute(f'''
                UPDATE user_configs SET {', '.join(updates)} WHERE username = ?
            ''', values)
        else:
            cursor.execute('''
                INSERT INTO user_configs (username, protocol_meta, settings, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (
                username,
                json.dumps(protocol_meta or {}, ensure_ascii=False),
                json.dumps(settings or {}, ensure_ascii=False),
                now
            ))
        
        conn.commit()
        return True


# ============================================================
# 数据迁移
# ============================================================

def migrate_from_json():
    """从 JSON 文件迁移数据到 SQLite"""
    import hashlib
    
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    users_json = os.path.join(data_dir, 'users.json')
    
    # 迁移用户
    if os.path.exists(users_json):
        print('迁移用户数据...')
        with open(users_json, 'r', encoding='utf-8') as f:
            users = json.load(f)
        
        for username, user_data in users.items():
            existing = db_get_user(username)
            if not existing:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO users (username, password_hash, display_name, email, role, 
                                          is_active, created_at, last_login)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_data['username'],
                        user_data['password_hash'],
                        user_data.get('display_name', username),
                        user_data.get('email', ''),
                        user_data.get('role', 'user'),
                        1 if user_data.get('is_active', True) else 0,
                        user_data.get('created_at'),
                        user_data.get('last_login')
                    ))
                    conn.commit()
                print(f'  迁移用户: {username}')
    
    # 迁移用户配置（设备树）
    for filename in os.listdir(data_dir):
        if filename.startswith('current_config_') and filename.endswith('.json'):
            username = filename.replace('current_config_', '').replace('.json', '')
            config_path = os.path.join(data_dir, filename)
            
            print(f'迁移用户配置: {username}')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 保存协议元信息
            protocol_meta = config.get('protocol_meta', {})
            db_save_user_config(username, protocol_meta=protocol_meta)
            
            # 迁移设备树
            device_tree = config.get('device_tree', [])
            _migrate_device_tree(device_tree, None)
    
    print('数据迁移完成!')


def _migrate_device_tree(nodes, parent_pk):
    """递归迁移设备树"""
    for node in nodes:
        device_id = node.get('id', '')
        name = node.get('name', '')
        is_device = node.get('is_device', False)
        
        # 检查是否已存在
        existing = db_get_device(device_id)
        if existing:
            device_pk = existing['id']
        else:
            device_pk = db_create_device(
                device_id=device_id,
                name=name,
                parent_id=parent_pk,
                is_device=is_device,
                device_version=node.get('device_version', 'V1.0'),
                current_version_name=node.get('current_version_name', ''),
                description=node.get('description', '')
            )
        
        if device_pk:
            # 保存协议版本
            for ver in node.get('versions', []):
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                            INSERT INTO device_protocol_versions (device_id, version_name, version)
                            VALUES (?, ?, ?)
                        ''', (device_pk, ver.get('name', ''), ver.get('version', '')))
                        conn.commit()
                    except sqlite3.IntegrityError:
                        pass
            
            # 保存 Labels
            labels = node.get('labels', [])
            if labels:
                db_save_labels(device_id, labels)
            
            # 保存版本历史
            for history in node.get('version_history', []):
                db_add_version_history(
                    device_id,
                    history.get('version', ''),
                    history.get('updated_by', ''),
                    history.get('change_summary', ''),
                    history.get('diff_summary', {}),
                    history.get('label_snapshot', [])
                )
        
        # 递归处理子节点
        children = node.get('children', [])
        if children:
            _migrate_device_tree(children, device_pk)


# 初始化时自动创建表
if __name__ == '__main__':
    init_database()
    print('数据库初始化完成')
    
    # 如果有旧数据，执行迁移
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'migrate':
        migrate_from_json()
