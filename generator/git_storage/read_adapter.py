# -*- coding: utf-8 -*-
"""
读取适配器
支持从 Git 优先读取设备信息、版本历史和快照
"""

import os
from typing import Optional, List, Dict

from .config import GitStorageConfig, extract_ata_code
from .device_storage import DeviceStorage, get_device_storage
from .version_manager import VersionManager, get_version_manager
from .save_adapter import is_git_storage_enabled


class ReadAdapter:
    """读取适配器
    
    支持两种模式：
    1. 数据库优先（默认）- 从数据库读取，Git 作为备份
    2. Git 优先 - 从 Git 读取，数据库作为索引
    """
    
    def __init__(self, 
                 device_storage: Optional[DeviceStorage] = None,
                 version_manager: Optional[VersionManager] = None):
        self.device_storage = device_storage or get_device_storage()
        self.version_manager = version_manager or get_version_manager()
    
    def get_device_labels(
        self,
        device_id: str,
        db_get_func=None,
        prefer_git: bool = False
    ) -> List[dict]:
        """获取设备 Labels
        
        Args:
            device_id: 设备 ID
            db_get_func: 数据库获取函数
            prefer_git: 是否优先从 Git 读取
        
        Returns:
            Labels 列表
        """
        # 如果启用了 Git 存储且优先 Git
        if is_git_storage_enabled() and prefer_git:
            ata_code = extract_ata_code(device_id)
            if ata_code:
                git_labels = self.device_storage.get_labels(ata_code, device_id)
                if git_labels:
                    return git_labels
        
        # 回退到数据库
        if db_get_func:
            return db_get_func() or []
        
        return []
    
    def get_device_info(
        self,
        device_id: str,
        db_get_func=None,
        prefer_git: bool = False
    ) -> Optional[dict]:
        """获取设备信息
        
        Args:
            device_id: 设备 ID
            db_get_func: 数据库获取函数
            prefer_git: 是否优先从 Git 读取
        
        Returns:
            设备信息字典
        """
        result = {}
        
        # 先从数据库获取基础信息
        if db_get_func:
            db_info = db_get_func()
            if db_info:
                result.update(db_info)
        
        # 如果启用了 Git 存储，补充 Git 信息
        if is_git_storage_enabled():
            git_info = self.version_manager.get_device_info(device_id)
            if git_info:
                # 补充 Git 特有的字段
                result['base_commit'] = git_info.get('base_commit', '')
                result['git_version'] = git_info.get('current_version', '')
                
                # 如果优先 Git，用 Git 的数据覆盖
                if prefer_git:
                    result['labels'] = git_info.get('labels', result.get('labels', []))
                    result['device_version'] = git_info.get('current_version', result.get('device_version', 'V1.0'))
        
        return result if result else None
    
    def get_version_history(
        self,
        device_id: str,
        db_get_func=None,
        prefer_git: bool = False,
        limit: int = 20
    ) -> List[dict]:
        """获取版本历史
        
        Args:
            device_id: 设备 ID
            db_get_func: 数据库获取函数
            prefer_git: 是否优先从 Git 读取
            limit: 返回记录数限制
        
        Returns:
            版本历史列表
        """
        # 如果启用了 Git 存储且优先 Git
        if is_git_storage_enabled() and prefer_git:
            git_history = self.version_manager.get_device_version_history(device_id, limit)
            if git_history:
                return git_history
        
        # 回退到数据库
        if db_get_func:
            return db_get_func() or []
        
        return []
    
    def get_version_snapshot(
        self,
        device_id: str,
        version: str,
        db_get_func=None,
        prefer_git: bool = False
    ) -> Optional[dict]:
        """获取版本快照
        
        Args:
            device_id: 设备 ID
            version: 版本号
            db_get_func: 数据库获取函数
            prefer_git: 是否优先从 Git 读取
        
        Returns:
            版本快照
        """
        # 如果启用了 Git 存储且优先 Git
        if is_git_storage_enabled() and prefer_git:
            git_snapshot = self.version_manager.get_version_snapshot(device_id, version)
            if git_snapshot:
                # 返回 labels 列表（兼容现有格式）
                return git_snapshot.get('labels', [])
        
        # 回退到数据库
        if db_get_func:
            return db_get_func()
        
        return None


# 全局单例
_read_adapter: Optional[ReadAdapter] = None


def get_read_adapter() -> ReadAdapter:
    """获取全局 ReadAdapter 实例"""
    global _read_adapter
    if _read_adapter is None:
        _read_adapter = ReadAdapter()
    return _read_adapter
