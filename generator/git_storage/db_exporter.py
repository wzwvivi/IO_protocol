# -*- coding: utf-8 -*-
"""
数据库导出器
将现有数据库数据导出到 ATA Git repo 目录结构
"""

import os
import sys
import json
import re
from typing import Optional, List, Dict, Tuple
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (
    db_get_device_tree, db_get_device, db_get_labels,
    db_get_version_history, get_db_connection
)

from .config import (
    GitStorageConfig, DeviceMeta, ReleaseRecord, ChangeStats, RepoMeta,
    extract_ata_code, get_ata_info, ATA_SYSTEMS,
    DEVICES_DIR, DEVICE_META_FILE, CURRENT_DIR, PROTOCOL_FILE,
    LABELS_DIR, VERSIONS_DIR, HISTORY_DIR, RELEASES_FILE, DOCS_DIR,
    REPO_META_FILE
)
from .repo_manager import ATARepoManager
from .device_storage import DeviceStorage


class DatabaseExporter:
    """数据库导出器"""
    
    def __init__(self, config: Optional[GitStorageConfig] = None):
        self.config = config or GitStorageConfig()
        self.repo_manager = ATARepoManager(self.config)
        self.device_storage = DeviceStorage(self.config, self.repo_manager)
        
        # 统计信息
        self.stats = {
            'ata_repos_created': 0,
            'devices_exported': 0,
            'labels_exported': 0,
            'versions_exported': 0,
            'errors': []
        }
    
    def export_all(self, dry_run: bool = False) -> Dict:
        """导出所有数据
        
        Args:
            dry_run: 如果为 True，只分析不实际写入
        
        Returns:
            导出统计信息
        """
        print('=' * 60)
        print('开始导出数据库到 Git 仓库')
        print('=' * 60)
        print()
        
        # 1. 获取设备树
        device_tree = db_get_device_tree()
        if not device_tree:
            print('警告: 数据库中没有设备数据')
            return self.stats
        
        # 2. 分析设备树，按 ATA 分组
        ata_devices = self._group_devices_by_ata(device_tree)
        
        print(f'发现 {len(ata_devices)} 个 ATA 系统:')
        for ata_code, devices in ata_devices.items():
            print(f'  - {ata_code.upper()}: {len(devices)} 个设备')
        print()
        
        if dry_run:
            print('[DRY RUN] 仅分析，不实际写入')
            return self.stats
        
        # 3. 确保仓库根目录存在
        self.repo_manager.ensure_repos_root()
        
        # 4. 导出每个 ATA
        for ata_code, devices in ata_devices.items():
            self._export_ata(ata_code, devices)
        
        # 5. 打印统计
        print()
        print('=' * 60)
        print('导出完成')
        print('=' * 60)
        print(f'  ATA 仓库创建: {self.stats["ata_repos_created"]}')
        print(f'  设备导出: {self.stats["devices_exported"]}')
        print(f'  Labels 导出: {self.stats["labels_exported"]}')
        print(f'  版本记录导出: {self.stats["versions_exported"]}')
        
        if self.stats['errors']:
            print(f'  错误数: {len(self.stats["errors"])}')
            for error in self.stats['errors'][:10]:
                print(f'    - {error}')
        
        return self.stats
    
    def _group_devices_by_ata(self, device_tree: List[dict]) -> Dict[str, List[dict]]:
        """将设备按 ATA 分组
        
        Returns:
            {ata_code: [device_info, ...]}
        """
        ata_devices = {}
        
        def process_node(node, parent_path=None):
            if parent_path is None:
                parent_path = []
            
            device_id = node.get('device_id') or node.get('id', '')
            name = node.get('name', '')
            is_device = node.get('is_device', False)
            
            current_path = parent_path + [name]
            
            if is_device:
                # 提取 ATA 代码
                ata_code = extract_ata_code(device_id)
                if not ata_code:
                    # 尝试从路径提取
                    for part in current_path:
                        match = re.match(r'ATA(\d+)', part, re.IGNORECASE)
                        if match:
                            ata_code = f'ata{match.group(1)}'
                            break
                
                if ata_code:
                    if ata_code not in ata_devices:
                        ata_devices[ata_code] = []
                    
                    ata_devices[ata_code].append({
                        'device_id': device_id,
                        'name': name,
                        'parent_path': current_path[:-1],  # 不包含自己
                        'device_version': node.get('device_version', 'V1.0'),
                        'current_version_name': node.get('current_version_name', ''),
                        'description': node.get('description', ''),
                        'node': node
                    })
            
            # 递归处理子节点
            for child in node.get('children', []):
                process_node(child, current_path)
        
        for node in device_tree:
            process_node(node)
        
        return ata_devices
    
    def _export_ata(self, ata_code: str, devices: List[dict]):
        """导出单个 ATA 的所有设备"""
        print(f'\n导出 {ata_code.upper()}...')
        
        # 1. 初始化 ATA 仓库
        ata_info = get_ata_info(ata_code)
        ata_name = ata_info['name'] if ata_info else f'{ata_code.upper()} 系统'
        
        success, msg = self.repo_manager.init_repo(ata_code, ata_name)
        if success:
            self.stats['ata_repos_created'] += 1
            print(f'  仓库初始化: {msg}')
        else:
            self.stats['errors'].append(f'{ata_code}: {msg}')
            print(f'  仓库初始化失败: {msg}')
            return
        
        # 2. 导出每个设备
        for device_info in devices:
            self._export_device(ata_code, device_info)
        
        # 3. 提交所有更改
        self.repo_manager.git_add(ata_code)
        success, msg, commit_hash = self.repo_manager.git_commit(
            ata_code,
            f'从数据库导入 {len(devices)} 个设备'
        )
        if success:
            print(f'  Git 提交: {commit_hash[:8] if commit_hash else "无更改"}')
    
    def _export_device(self, ata_code: str, device_info: dict):
        """导出单个设备"""
        device_id = device_info['device_id']
        device_name = device_info['name']
        
        print(f'    导出设备: {device_id} ({device_name})')
        
        try:
            # 1. 初始化设备目录
            success, msg = self.device_storage.init_device(
                ata_code=ata_code,
                device_id=device_id,
                device_name=device_name,
                parent_path=device_info.get('parent_path', []),
                description=device_info.get('description', ''),
                protocol_version_name=device_info.get('current_version_name', '')
            )
            
            if not success:
                self.stats['errors'].append(f'{device_id}: {msg}')
                return
            
            # 2. 获取并保存 Labels
            labels = db_get_labels(device_id)
            if labels:
                self.device_storage.save_labels(ata_code, device_id, labels, split_files=True)
                self.stats['labels_exported'] += len(labels)
                
                # 同时保存到 protocol.json
                self.device_storage.save_current_protocol(
                    ata_code, device_id,
                    protocol_meta={
                        'name': device_name,
                        'version': device_info.get('device_version', 'V1.0'),
                        'description': device_info.get('description', '')
                    },
                    labels=labels,
                    version_info={
                        'version': device_info.get('device_version', 'V1.0'),
                        'created_at': datetime.now().isoformat()
                    }
                )
            
            # 3. 更新设备元数据
            device_meta = self.device_storage.get_device_meta(ata_code, device_id)
            if device_meta:
                device_meta.current_version = device_info.get('device_version', 'V1.0')
                device_meta.current_protocol_version_name = device_info.get('current_version_name', '')
                self.device_storage.save_device_meta(ata_code, device_id, device_meta)
            
            # 4. 导出版本历史
            version_history = db_get_version_history(device_id)
            if version_history:
                self._export_version_history(ata_code, device_id, version_history)
            
            self.stats['devices_exported'] += 1
            
        except Exception as e:
            self.stats['errors'].append(f'{device_id}: {str(e)}')
            print(f'      错误: {str(e)}')
    
    def _export_version_history(self, ata_code: str, device_id: str, 
                                version_history: List[dict]):
        """导出版本历史"""
        for record in version_history:
            version = record.get('version', '')
            if not version:
                continue
            
            # 1. 保存版本快照
            snapshot = record.get('label_snapshot', [])
            if snapshot:
                snapshot_data = {
                    'version': version,
                    'created_at': record.get('updated_at', ''),
                    'created_by': record.get('updated_by', ''),
                    'labels': snapshot,
                    'label_count': len(snapshot)
                }
                self.device_storage.save_version_snapshot(ata_code, device_id, version, snapshot_data)
            
            # 2. 添加发布记录
            change_stats = record.get('change_stats', {})
            if isinstance(change_stats, dict):
                stats = ChangeStats(
                    added=change_stats.get('added', 0),
                    modified=change_stats.get('modified', 0),
                    deleted=change_stats.get('deleted', 0)
                )
            else:
                stats = ChangeStats()
            
            release = ReleaseRecord(
                release_id=f'{device_id}_{version.lower().replace(".", "_")}',
                device_id=device_id,
                from_version='',  # 旧数据可能没有
                to_version=version,
                summary=record.get('change_summary', ''),
                change_stats=stats,
                git_commit='',  # 导入时没有
                git_tag='',
                created_by=record.get('updated_by', ''),
                created_at=record.get('updated_at', ''),
                label_count=record.get('label_count', len(record.get('label_snapshot', [])))
            )
            
            self.device_storage.add_release(ata_code, device_id, release)
            self.stats['versions_exported'] += 1


def export_database_to_git(dry_run: bool = False) -> Dict:
    """导出数据库到 Git 仓库的便捷函数"""
    exporter = DatabaseExporter()
    return exporter.export_all(dry_run=dry_run)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='导出数据库到 Git 仓库')
    parser.add_argument('--dry-run', action='store_true', help='仅分析，不实际写入')
    args = parser.parse_args()
    
    export_database_to_git(dry_run=args.dry_run)
