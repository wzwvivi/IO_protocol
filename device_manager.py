# -*- coding: utf-8 -*-
"""
设备树管理模块
负责设备树的导入、存储、版本管理
支持 SQLite 数据库存储
"""

import os
import json
import copy
import re
from datetime import datetime

from database import (
    db_get_device, db_create_device, db_update_device,
    db_get_device_tree, db_get_labels, db_save_labels,
    db_add_version_history, db_get_version_history, db_get_version_snapshot,
    get_db_connection
)


def generate_device_id(path_parts):
    """根据路径生成稳定的设备ID
    
    Args:
        path_parts: 路径组成部分列表，如 ['ATA32-起落架系统', '32-3-转弯控制单元']
    Returns:
        稳定的设备ID字符串
    """
    id_parts = []
    for part in path_parts:
        match = re.match(r'ATA(\d+)', part)
        if match:
            id_parts.append(f'ata{match.group(1)}')
            continue
        
        match = re.match(r'(\d+)-(\d+)', part)
        if match:
            id_parts.append(f'{match.group(1)}_{match.group(2)}')
            continue
        
        clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', part)
        clean_name = re.sub(r'_+', '_', clean_name).strip('_').lower()
        if clean_name:
            id_parts.append(clean_name[:20])
    
    return '_'.join(id_parts) if id_parts else 'unknown'


def is_protocol_version_dir(dirname):
    """判断目录名是否是协议版本目录"""
    if re.search(r'[Vv]\d+\.?\d*', dirname):
        return True
    if '协议' in dirname or 'Protocol' in dirname.lower():
        return True
    return False


def extract_version_from_dirname(dirname):
    """从目录名提取版本号"""
    match = re.search(r'[Vv](\d+\.?\d*\.?\d*)', dirname)
    if match:
        return f'V{match.group(1)}'
    return 'V1.0'


def scan_directory_tree(root_path, current_path=None, path_parts=None, depth=0):
    """扫描目录树，生成设备节点结构"""
    if current_path is None:
        current_path = root_path
    if path_parts is None:
        path_parts = []
    
    nodes = []
    
    try:
        entries = sorted(os.listdir(current_path))
    except (PermissionError, FileNotFoundError):
        return nodes
    
    for entry in entries:
        entry_path = os.path.join(current_path, entry)
        
        if not os.path.isdir(entry_path):
            continue
        if entry.startswith('.') or entry.startswith('~'):
            continue
        
        current_parts = path_parts + [entry]
        
        subdirs = [d for d in os.listdir(entry_path) 
                   if os.path.isdir(os.path.join(entry_path, d)) 
                   and not d.startswith('.')]
        
        all_versions = len(subdirs) > 0 and all(is_protocol_version_dir(d) for d in subdirs)
        
        if len(subdirs) == 0:
            node = {
                'id': generate_device_id(current_parts),
                'name': entry,
                'is_device': True,
                'device_version': extract_version_from_dirname(entry),
                'version_history': [],
                'labels': [],
            }
            nodes.append(node)
        elif all_versions:
            versions = []
            for subdir in sorted(subdirs):
                version_name = extract_version_from_dirname(subdir)
                versions.append({
                    'name': subdir,
                    'version': version_name,
                    'labels': []
                })
            
            latest_version = versions[-1] if versions else {'version': 'V1.0', 'labels': []}
            
            node = {
                'id': generate_device_id(current_parts),
                'name': entry,
                'is_device': True,
                'device_version': latest_version['version'],
                'current_version_name': latest_version.get('name', ''),
                'versions': versions,
                'version_history': [],
                'labels': [],
            }
            nodes.append(node)
        else:
            node = {
                'id': generate_device_id(current_parts),
                'name': entry,
                'is_device': False,
                'children': scan_directory_tree(root_path, entry_path, current_parts, depth + 1)
            }
            nodes.append(node)
    
    return nodes


def import_device_tree_from_directory(data_protocol_path):
    """从数据协议目录导入设备树"""
    if not os.path.exists(data_protocol_path):
        return []
    
    return scan_directory_tree(data_protocol_path)


def save_device_tree_to_db(device_tree, parent_pk=None):
    """将设备树保存到数据库"""
    for node in device_tree:
        device_id = node.get('id', '')
        name = node.get('name', '')
        is_device = node.get('is_device', False)
        
        existing = db_get_device(device_id)
        if existing:
            device_pk = existing['id']
            db_update_device(
                device_id,
                name=name,
                device_version=node.get('device_version', 'V1.0'),
                current_version_name=node.get('current_version_name', '')
            )
        else:
            device_pk = db_create_device(
                device_id=device_id,
                name=name,
                parent_id=parent_pk,
                is_device=is_device,
                device_version=node.get('device_version', 'V1.0'),
                current_version_name=node.get('current_version_name', '')
            )
        
        if device_pk:
            # 保存协议版本
            for ver in node.get('versions', []):
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO device_protocol_versions (device_id, version_name, version)
                            VALUES (?, ?, ?)
                        ''', (device_pk, ver.get('name', ''), ver.get('version', '')))
                        conn.commit()
                    except:
                        pass
            
            # 保存 Labels
            labels = node.get('labels', [])
            if labels:
                db_save_labels(device_id, labels)
        
        # 递归处理子节点
        children = node.get('children', [])
        if children:
            save_device_tree_to_db(children, device_pk)


def get_device_tree_from_db():
    """从数据库获取设备树"""
    return db_get_device_tree()


def find_device_node(device_tree, device_id):
    """在设备树中查找指定ID的设备节点"""
    for node in device_tree:
        if node.get('id') == device_id or node.get('device_id') == device_id:
            return node, device_tree
        
        if 'children' in node:
            result, parent = find_device_node(node['children'], device_id)
            if result:
                return result, parent
    
    return None, None


def find_device_by_path(device_tree, path_parts):
    """根据路径部分查找设备节点"""
    if not path_parts:
        return None
    
    current_nodes = device_tree
    target_node = None
    
    for part in path_parts:
        found = False
        for node in current_nodes:
            if node['name'] == part:
                target_node = node
                current_nodes = node.get('children', [])
                found = True
                break
        if not found:
            return None
    
    return target_node


def get_all_devices(device_tree, result=None):
    """获取所有设备节点（叶子节点）"""
    if result is None:
        result = []
    
    for node in device_tree:
        if node.get('is_device', False):
            result.append(node)
        elif 'children' in node:
            get_all_devices(node['children'], result)
    
    return result


def compute_field_diff(old_value, new_value, path=""):
    """计算两个值之间的字段级差异"""
    changes = []
    
    if type(old_value) != type(new_value):
        changes.append({
            'field': path or '值',
            'old': str(old_value)[:100],
            'new': str(new_value)[:100]
        })
        return changes
    
    if isinstance(old_value, dict):
        all_keys = set(old_value.keys()) | set(new_value.keys())
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            if key not in old_value:
                changes.append({
                    'field': new_path,
                    'old': '(无)',
                    'new': str(new_value[key])[:100]
                })
            elif key not in new_value:
                changes.append({
                    'field': new_path,
                    'old': str(old_value[key])[:100],
                    'new': '(已删除)'
                })
            else:
                changes.extend(compute_field_diff(old_value[key], new_value[key], new_path))
    elif isinstance(old_value, list):
        if old_value != new_value:
            changes.append({
                'field': path or '列表',
                'old': str(old_value)[:100],
                'new': str(new_value)[:100]
            })
    else:
        if old_value != new_value:
            changes.append({
                'field': path or '值',
                'old': str(old_value)[:100],
                'new': str(new_value)[:100]
            })
    
    return changes


def compute_labels_diff(old_labels, new_labels):
    """计算两个 labels 列表的差异"""
    old_map = {label.get('label_oct', ''): label for label in old_labels if label.get('label_oct')}
    new_map = {label.get('label_oct', ''): label for label in new_labels if label.get('label_oct')}
    
    old_octs = set(old_map.keys())
    new_octs = set(new_map.keys())
    
    added_details = []
    for oct_val in sorted(new_octs - old_octs):
        label = new_map[oct_val]
        added_details.append({
            'label_oct': oct_val,
            'name': label.get('name', ''),
            'direction': label.get('direction', '')
        })
    
    removed_details = []
    for oct_val in sorted(old_octs - new_octs):
        label = old_map[oct_val]
        removed_details.append({
            'label_oct': oct_val,
            'name': label.get('name', ''),
            'direction': label.get('direction', '')
        })
    
    modified_details = []
    for oct_val in sorted(old_octs & new_octs):
        old_label = old_map[oct_val]
        new_label = new_map[oct_val]
        
        if json.dumps(old_label, sort_keys=True) != json.dumps(new_label, sort_keys=True):
            field_changes = compute_field_diff(old_label, new_label)
            important_changes = [c for c in field_changes if c['field'] not in ['data_type']]
            
            if important_changes:
                modified_details.append({
                    'label_oct': oct_val,
                    'name': new_label.get('name', old_label.get('name', '')),
                    'changes': important_changes[:10]
                })
    
    return {
        'added': [d['label_oct'] for d in added_details],
        'added_details': added_details,
        'removed': [d['label_oct'] for d in removed_details],
        'removed_details': removed_details,
        'modified': [d['label_oct'] for d in modified_details],
        'modified_details': modified_details
    }


def has_labels_changed(old_labels, new_labels):
    """检查 labels 是否有变化"""
    diff = compute_labels_diff(old_labels, new_labels)
    return bool(diff['added'] or diff['removed'] or diff['modified'])


def increment_version(version_str):
    """版本号主版本升级"""
    match = re.match(r'([Vv]?)(\d+)\.?(\d*)', version_str)
    if not match:
        return 'V2.0'
    
    prefix = match.group(1) or 'V'
    major = int(match.group(2))
    major += 1
    
    return f'{prefix}{major}.0'


def create_version_record(old_labels, new_labels, version, username=None, change_summary=None):
    """创建版本记录"""
    diff = compute_labels_diff(old_labels, new_labels)
    
    if not change_summary:
        parts = []
        if diff['added']:
            parts.append(f"新增 {len(diff['added'])} 个 Label")
        if diff['removed']:
            parts.append(f"删除 {len(diff['removed'])} 个 Label")
        if diff['modified']:
            parts.append(f"修改 {len(diff['modified'])} 个 Label")
        change_summary = '；'.join(parts) if parts else '无变更'
    
    return {
        'version': version,
        'updated_at': datetime.now().isoformat(),
        'updated_by': username or 'unknown',
        'change_summary': change_summary,
        'diff_summary': diff,
        'label_snapshot': copy.deepcopy(old_labels),
        'label_count': len(old_labels)
    }


def update_device_version(device_node, new_labels, username=None, 
                          new_version=None, change_summary=None,
                          save_labels=True, protocol_version_id=None):
    """更新设备版本
    
    Args:
        device_node: 设备节点数据
        new_labels: 新的 Labels 列表
        username: 操作用户名
        new_version: 指定的新版本号（可选）
        change_summary: 变更说明（可选）
        save_labels: 是否保存 Labels 到数据库（默认 True）
        protocol_version_id: 协议版本 ID（用于保存 Labels）
    
    Returns:
        (changed, version): 是否有变化，新版本号
    """
    device_id = device_node.get('id') or device_node.get('device_id')
    old_labels = device_node.get('labels', [])
    
    # 如果是数据库模式，从数据库获取旧 labels
    if not old_labels and device_id:
        old_labels = db_get_labels(device_id, protocol_version_id)
    
    if not has_labels_changed(old_labels, new_labels):
        device_node['labels'] = new_labels
        # 即使没有变化，也需要保存（可能是首次保存）
        if save_labels and device_id:
            db_save_labels(device_id, new_labels, protocol_version_id)
        return False, device_node.get('device_version', 'V1.0')
    
    current_version = device_node.get('device_version', 'V1.0')
    
    if new_version:
        next_version = new_version
    else:
        next_version = increment_version(current_version)
    
    version_record = create_version_record(
        old_labels, new_labels, current_version, username, change_summary
    )
    
    # 更新内存中的节点
    if 'version_history' not in device_node:
        device_node['version_history'] = []
    
    device_node['version_history'].insert(0, version_record)
    device_node['device_version'] = next_version
    device_node['labels'] = new_labels
    
    # 保存到数据库
    if device_id:
        # 先保存版本历史（记录旧版本的快照）
        db_add_version_history(
            device_id,
            current_version,
            username,
            version_record['change_summary'],
            version_record['diff_summary'],
            old_labels
        )
        
        # 更新设备版本号
        db_update_device(device_id, device_version=next_version)
        
        # 保存新的 Labels（如果需要）
        if save_labels:
            db_save_labels(device_id, new_labels, protocol_version_id)
    
    return True, next_version


def migrate_legacy_config(config, target_device_id='ata32_32_3'):
    """将旧格式配置迁移到新格式"""
    if 'device_tree' in config and config['device_tree']:
        return config
    
    old_labels = config.get('labels', [])
    
    device_tree = [
        {
            'id': 'ata32',
            'name': 'ATA32-起落架系统',
            'is_device': False,
            'children': [
                {
                    'id': 'ata32_32_1',
                    'name': '32-1-刹车控制单元',
                    'is_device': True,
                    'device_version': 'V1.0',
                    'version_history': [],
                    'labels': []
                },
                {
                    'id': 'ata32_32_2',
                    'name': '32-2-收放控制单元',
                    'is_device': True,
                    'device_version': 'V1.0',
                    'version_history': [],
                    'labels': []
                },
                {
                    'id': 'ata32_32_3',
                    'name': '32-3-转弯控制单元',
                    'is_device': True,
                    'device_version': config.get('protocol_meta', {}).get('version', 'V1.0'),
                    'version_history': [],
                    'labels': old_labels
                }
            ]
        }
    ]
    
    new_config = {
        'protocol_meta': config.get('protocol_meta', {
            'name': 'ARINC429 协议配置',
            'version': 'V1.0',
            'description': ''
        }),
        'device_tree': device_tree
    }
    
    if old_labels:
        new_config['labels'] = old_labels
    
    return new_config


def get_device_labels_for_generation(config, device_id=None):
    """获取用于代码生成的 labels 列表"""
    if 'device_tree' not in config or not config['device_tree']:
        return config.get('labels', [])
    
    if device_id:
        # 先尝试从数据库获取
        labels = db_get_labels(device_id)
        if labels:
            return labels
        
        # 回退到内存中的设备树
        node, _ = find_device_node(config['device_tree'], device_id)
        if node and node.get('is_device', False):
            return node.get('labels', [])
        return []
    else:
        all_labels = []
        devices = get_all_devices(config['device_tree'])
        for device in devices:
            device_id = device.get('id') or device.get('device_id')
            if device_id:
                labels = db_get_labels(device_id)
                if labels:
                    all_labels.extend(labels)
                    continue
            all_labels.extend(device.get('labels', []))
        return all_labels
