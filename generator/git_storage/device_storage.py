# -*- coding: utf-8 -*-
"""
设备存储模块
负责设备协议文件的读写操作
"""

import os
import json
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from .config import (
    GitStorageConfig, DeviceMeta, LabelDefinition,
    ProtocolMeta, VersionInfo, ReleaseRecord, ChangeStats, SaveRecord,
    DEVICES_DIR, DEVICE_META_FILE, CURRENT_DIR, PROTOCOL_FILE,
    LABELS_DIR, VERSIONS_DIR, HISTORY_DIR, RELEASES_FILE, SAVES_FILE, DOCS_DIR,
    extract_ata_code, generate_release_id, generate_git_tag, generate_save_id
)
from .repo_manager import ATARepoManager, get_repo_manager


class DeviceStorage:
    """设备存储管理"""
    
    def __init__(self, config: Optional[GitStorageConfig] = None,
                 repo_manager: Optional[ATARepoManager] = None):
        self.config = config or GitStorageConfig()
        self.repo_manager = repo_manager or get_repo_manager()
    
    def _ensure_device_dirs(self, ata_code: str, device_id: str):
        """确保设备目录结构存在"""
        device_path = self.config.get_device_path(ata_code, device_id)
        
        # 创建所有必要的子目录
        dirs_to_create = [
            device_path,
            os.path.join(device_path, CURRENT_DIR),
            os.path.join(device_path, CURRENT_DIR, LABELS_DIR),
            os.path.join(device_path, VERSIONS_DIR),
            os.path.join(device_path, HISTORY_DIR),
            os.path.join(device_path, DOCS_DIR),
        ]
        
        for dir_path in dirs_to_create:
            os.makedirs(dir_path, exist_ok=True)
    
    def device_exists(self, ata_code: str, device_id: str) -> bool:
        """检查设备是否存在"""
        device_path = self.config.get_device_path(ata_code, device_id)
        meta_path = os.path.join(device_path, DEVICE_META_FILE)
        return os.path.exists(meta_path)
    
    def init_device(self, ata_code: str, device_id: str, device_name: str,
                    parent_path: List[str] = None, description: str = '',
                    protocol_version_name: str = '') -> Tuple[bool, str]:
        """初始化设备目录
        
        Args:
            ata_code: ATA 代码
            device_id: 设备 ID
            device_name: 设备名称
            parent_path: 父路径列表
            description: 设备描述
            protocol_version_name: 协议版本名称
        
        Returns:
            (success, message)
        """
        # 确保 ATA 仓库存在
        if not self.repo_manager.repo_exists(ata_code):
            success, msg = self.repo_manager.init_repo(ata_code)
            if not success:
                return False, msg
        
        # 创建目录结构
        self._ensure_device_dirs(ata_code, device_id)
        
        # 创建设备元数据
        device_meta = DeviceMeta(
            device_id=device_id,
            device_name=device_name,
            ata_code=ata_code.upper(),
            parent_path=parent_path or [],
            current_version='V1.0',
            current_protocol_version_name=protocol_version_name,
            description=description,
            updated_at=datetime.now().isoformat(),
            status='active'
        )
        
        self.save_device_meta(ata_code, device_id, device_meta)
        
        # 创建空的 releases.json
        releases_path = os.path.join(
            self.config.get_device_history_path(ata_code, device_id),
            RELEASES_FILE
        )
        if not os.path.exists(releases_path):
            with open(releases_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        
        return True, f'设备 {device_id} 初始化成功'
    
    def get_device_meta(self, ata_code: str, device_id: str) -> Optional[DeviceMeta]:
        """获取设备元数据"""
        device_path = self.config.get_device_path(ata_code, device_id)
        meta_path = os.path.join(device_path, DEVICE_META_FILE)
        
        if not os.path.exists(meta_path):
            return None
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return DeviceMeta.from_dict(data)
        except Exception:
            return None
    
    def save_device_meta(self, ata_code: str, device_id: str, 
                         meta: DeviceMeta) -> bool:
        """保存设备元数据"""
        device_path = self.config.get_device_path(ata_code, device_id)
        meta_path = os.path.join(device_path, DEVICE_META_FILE)
        
        try:
            os.makedirs(device_path, exist_ok=True)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get_current_protocol(self, ata_code: str, device_id: str) -> Optional[dict]:
        """获取当前协议完整内容"""
        current_path = self.config.get_device_current_path(ata_code, device_id)
        protocol_path = os.path.join(current_path, PROTOCOL_FILE)
        
        if not os.path.exists(protocol_path):
            return None
        
        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def save_current_protocol(self, ata_code: str, device_id: str,
                              protocol_meta: dict, labels: List[dict],
                              version_info: dict = None) -> bool:
        """保存当前协议
        
        Args:
            ata_code: ATA 代码
            device_id: 设备 ID
            protocol_meta: 协议元信息
            labels: Labels 列表
            version_info: 版本信息
        
        Returns:
            是否成功
        """
        self._ensure_device_dirs(ata_code, device_id)
        
        current_path = self.config.get_device_current_path(ata_code, device_id)
        protocol_path = os.path.join(current_path, PROTOCOL_FILE)
        
        # 获取设备元数据
        device_meta = self.get_device_meta(ata_code, device_id)
        
        protocol_data = {
            'protocol_meta': protocol_meta,
            'device_meta_ref': {
                'device_id': device_id,
                'ata_code': ata_code.upper()
            },
            'version_info': version_info or {
                'version': device_meta.current_version if device_meta else 'V1.0',
                'created_at': datetime.now().isoformat()
            },
            'labels': labels
        }
        
        try:
            with open(protocol_path, 'w', encoding='utf-8') as f:
                json.dump(protocol_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get_labels(self, ata_code: str, device_id: str) -> List[dict]:
        """获取设备的所有 Labels
        
        优先从 current/labels/ 目录读取拆分的文件，
        如果不存在则从 current/protocol.json 读取
        """
        labels_dir = self.config.get_device_labels_path(ata_code, device_id)
        
        # 尝试从拆分文件读取
        if os.path.exists(labels_dir):
            labels = []
            for filename in sorted(os.listdir(labels_dir)):
                if filename.endswith('.json'):
                    filepath = os.path.join(labels_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            label_data = json.load(f)
                            labels.append(label_data)
                    except Exception:
                        continue
            if labels:
                return labels
        
        # 回退到 protocol.json
        protocol = self.get_current_protocol(ata_code, device_id)
        if protocol:
            return protocol.get('labels', [])
        
        return []
    
    def save_labels(self, ata_code: str, device_id: str, 
                    labels: List[dict], split_files: bool = True) -> bool:
        """保存 Labels
        
        Args:
            ata_code: ATA 代码
            device_id: 设备 ID
            labels: Labels 列表
            split_files: 是否拆分为多个文件
        
        Returns:
            是否成功
        """
        self._ensure_device_dirs(ata_code, device_id)
        
        if split_files:
            return self._save_labels_split(ata_code, device_id, labels)
        else:
            return self._save_labels_single(ata_code, device_id, labels)
    
    def _save_labels_split(self, ata_code: str, device_id: str, 
                           labels: List[dict]) -> bool:
        """将 Labels 拆分保存为多个文件"""
        labels_dir = self.config.get_device_labels_path(ata_code, device_id)
        
        try:
            # 清空现有文件
            if os.path.exists(labels_dir):
                for filename in os.listdir(labels_dir):
                    if filename.endswith('.json'):
                        os.remove(os.path.join(labels_dir, filename))
            
            # 保存每个 Label
            for label in labels:
                label_oct = label.get('label_oct', '')
                if not label_oct:
                    continue
                
                # 使用 label_oct 作为文件名
                filename = f'{label_oct}.json'
                filepath = os.path.join(labels_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(label, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def _save_labels_single(self, ata_code: str, device_id: str,
                            labels: List[dict]) -> bool:
        """将 Labels 保存到 protocol.json"""
        protocol = self.get_current_protocol(ata_code, device_id) or {}
        protocol['labels'] = labels
        
        current_path = self.config.get_device_current_path(ata_code, device_id)
        protocol_path = os.path.join(current_path, PROTOCOL_FILE)
        
        try:
            with open(protocol_path, 'w', encoding='utf-8') as f:
                json.dump(protocol, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get_version_snapshot(self, ata_code: str, device_id: str, 
                             version: str) -> Optional[dict]:
        """获取版本快照"""
        versions_dir = self.config.get_device_versions_path(ata_code, device_id)
        version_file = os.path.join(versions_dir, f'{version}.json')
        
        if not os.path.exists(version_file):
            return None
        
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def save_version_snapshot(self, ata_code: str, device_id: str,
                              version: str, snapshot: dict) -> bool:
        """保存版本快照"""
        self._ensure_device_dirs(ata_code, device_id)
        
        versions_dir = self.config.get_device_versions_path(ata_code, device_id)
        version_file = os.path.join(versions_dir, f'{version}.json')
        
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def list_versions(self, ata_code: str, device_id: str) -> List[str]:
        """列出所有版本"""
        versions_dir = self.config.get_device_versions_path(ata_code, device_id)
        
        if not os.path.exists(versions_dir):
            return []
        
        versions = []
        for filename in os.listdir(versions_dir):
            if filename.endswith('.json'):
                version = filename[:-5]  # 去掉 .json
                versions.append(version)
        
        return sorted(versions)
    
    def get_releases(self, ata_code: str, device_id: str) -> List[ReleaseRecord]:
        """获取发布记录列表"""
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        releases_file = os.path.join(history_dir, RELEASES_FILE)
        
        if not os.path.exists(releases_file):
            return []
        
        try:
            with open(releases_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [ReleaseRecord.from_dict(r) for r in data]
        except Exception:
            return []
    
    def add_release(self, ata_code: str, device_id: str,
                    release: ReleaseRecord) -> bool:
        """添加发布记录"""
        self._ensure_device_dirs(ata_code, device_id)
        
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        releases_file = os.path.join(history_dir, RELEASES_FILE)
        
        try:
            # 读取现有记录
            releases = []
            if os.path.exists(releases_file):
                with open(releases_file, 'r', encoding='utf-8') as f:
                    releases = json.load(f)
            
            # 添加新记录到开头
            releases.insert(0, release.to_dict())
            
            # 保存
            with open(releases_file, 'w', encoding='utf-8') as f:
                json.dump(releases, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def update_latest_release_commit(self, ata_code: str, device_id: str, 
                                      commit_hash: str) -> bool:
        """更新最新发布记录的 git_commit 字段
        
        在 git commit 之后调用，将 commit hash 回填到 releases.json 的最新记录中
        """
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        releases_file = os.path.join(history_dir, RELEASES_FILE)
        
        if not os.path.exists(releases_file):
            return False
        
        try:
            with open(releases_file, 'r', encoding='utf-8') as f:
                releases = json.load(f)
            
            if releases and len(releases) > 0:
                # 更新第一条（最新）记录的 git_commit
                releases[0]['git_commit'] = commit_hash
                
                with open(releases_file, 'w', encoding='utf-8') as f:
                    json.dump(releases, f, ensure_ascii=False, indent=2)
                
                return True
            return False
        except Exception:
            return False
    
    def list_devices(self, ata_code: str) -> List[str]:
        """列出 ATA 下的所有设备"""
        repo_path = self.config.get_ata_repo_path(ata_code)
        devices_dir = os.path.join(repo_path, DEVICES_DIR)
        
        if not os.path.exists(devices_dir):
            return []
        
        devices = []
        for name in os.listdir(devices_dir):
            device_path = os.path.join(devices_dir, name)
            if os.path.isdir(device_path):
                meta_path = os.path.join(device_path, DEVICE_META_FILE)
                if os.path.exists(meta_path):
                    devices.append(name)
        
        return sorted(devices)
    
    def get_device_base_commit(self, ata_code: str, device_id: str) -> Optional[str]:
        """获取设备的最新 commit hash（用于乐观锁）"""
        return self.repo_manager.get_device_last_commit(ata_code, device_id)
    
    # ========== 保存记录相关方法 ==========
    
    def get_saves(self, ata_code: str, device_id: str) -> List[SaveRecord]:
        """获取保存记录列表（完整保存时间线）"""
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        saves_file = os.path.join(history_dir, SAVES_FILE)
        
        if not os.path.exists(saves_file):
            return []
        
        try:
            with open(saves_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [SaveRecord.from_dict(s) for s in data]
        except Exception:
            return []
    
    def add_save(self, ata_code: str, device_id: str, save: SaveRecord) -> bool:
        """添加保存记录"""
        self._ensure_device_dirs(ata_code, device_id)
        
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        saves_file = os.path.join(history_dir, SAVES_FILE)
        
        try:
            # 读取现有记录
            saves = []
            if os.path.exists(saves_file):
                with open(saves_file, 'r', encoding='utf-8') as f:
                    saves = json.load(f)
            
            # 添加新记录到开头
            saves.insert(0, save.to_dict())
            
            # 保存
            with open(saves_file, 'w', encoding='utf-8') as f:
                json.dump(saves, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def update_latest_save_commit(self, ata_code: str, device_id: str, 
                                   commit_hash: str) -> bool:
        """更新最新保存记录的 git_commit 字段"""
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        saves_file = os.path.join(history_dir, SAVES_FILE)
        
        if not os.path.exists(saves_file):
            return False
        
        try:
            with open(saves_file, 'r', encoding='utf-8') as f:
                saves = json.load(f)
            
            if saves and len(saves) > 0:
                saves[0]['git_commit'] = commit_hash
                
                with open(saves_file, 'w', encoding='utf-8') as f:
                    json.dump(saves, f, ensure_ascii=False, indent=2)
                
                return True
            return False
        except Exception:
            return False
    
    def delete_release(self, ata_code: str, device_id: str, version: str) -> Tuple[bool, str]:
        """删除指定版本的发布记录和快照
        
        使用强一致性校验：所有操作必须成功，否则回滚
        
        Args:
            ata_code: ATA 代码
            device_id: 设备 ID
            version: 要删除的版本号
            
        Returns:
            (success, message) 元组
        """
        history_dir = self.config.get_device_history_path(ata_code, device_id)
        versions_dir = self.config.get_device_versions_path(ata_code, device_id)
        
        releases_file = os.path.join(history_dir, RELEASES_FILE)
        saves_file = os.path.join(history_dir, SAVES_FILE)
        version_file = os.path.join(versions_dir, f'{version}.json')
        
        # 先检查版本是否存在
        version_exists = False
        
        if os.path.exists(version_file):
            version_exists = True
        
        if os.path.exists(releases_file):
            try:
                with open(releases_file, 'r', encoding='utf-8') as f:
                    releases = json.load(f)
                if any(r.get('to_version') == version for r in releases):
                    version_exists = True
            except Exception:
                pass
        
        if not version_exists:
            return False, f'版本 {version} 不存在'
        
        # 备份原始数据用于回滚
        backup_releases = None
        backup_saves = None
        
        try:
            # 1. 从 releases.json 中删除记录
            if os.path.exists(releases_file):
                with open(releases_file, 'r', encoding='utf-8') as f:
                    backup_releases = json.load(f)
                
                new_releases = [r for r in backup_releases if r.get('to_version') != version]
                with open(releases_file, 'w', encoding='utf-8') as f:
                    json.dump(new_releases, f, ensure_ascii=False, indent=2)
            
            # 2. 从 saves.json 中删除相关记录
            if os.path.exists(saves_file):
                with open(saves_file, 'r', encoding='utf-8') as f:
                    backup_saves = json.load(f)
                
                new_saves = [s for s in backup_saves if s.get('version') != version]
                with open(saves_file, 'w', encoding='utf-8') as f:
                    json.dump(new_saves, f, ensure_ascii=False, indent=2)
            
            # 3. 删除版本快照文件
            if os.path.exists(version_file):
                os.remove(version_file)
            
            return True, f'版本 {version} 已删除'
            
        except Exception as e:
            # 回滚：恢复原始数据
            try:
                if backup_releases is not None:
                    with open(releases_file, 'w', encoding='utf-8') as f:
                        json.dump(backup_releases, f, ensure_ascii=False, indent=2)
                if backup_saves is not None:
                    with open(saves_file, 'w', encoding='utf-8') as f:
                        json.dump(backup_saves, f, ensure_ascii=False, indent=2)
            except Exception:
                pass  # 回滚失败，记录日志但不抛出
            
            return False, f'删除失败: {str(e)}'


# 全局单例
_device_storage: Optional[DeviceStorage] = None


def get_device_storage() -> DeviceStorage:
    """获取全局 DeviceStorage 实例"""
    global _device_storage
    if _device_storage is None:
        _device_storage = DeviceStorage()
    return _device_storage
