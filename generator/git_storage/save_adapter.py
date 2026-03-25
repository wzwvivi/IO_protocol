# -*- coding: utf-8 -*-
"""
保存适配器
提供数据库和 Git 双写能力，支持渐进式迁移
"""

import os
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from .config import GitStorageConfig, extract_ata_code
from .version_manager import VersionManager, get_version_manager


# 全局开关：是否启用 Git 存储
# 默认启用，可以通过环境变量 ENABLE_GIT_STORAGE=0 禁用
GIT_STORAGE_ENABLED = os.environ.get('ENABLE_GIT_STORAGE', '1') == '1'


def is_git_storage_enabled() -> bool:
    """检查 Git 存储是否启用"""
    return GIT_STORAGE_ENABLED


def enable_git_storage():
    """启用 Git 存储"""
    global GIT_STORAGE_ENABLED
    GIT_STORAGE_ENABLED = True


def disable_git_storage():
    """禁用 Git 存储"""
    global GIT_STORAGE_ENABLED
    GIT_STORAGE_ENABLED = False


class SaveAdapter:
    """保存适配器
    
    支持三种模式：
    1. 仅数据库（默认）
    2. 双写（数据库 + Git）
    3. 仅 Git（未来）
    """
    
    def __init__(self, version_manager: Optional[VersionManager] = None):
        self.version_manager = version_manager or get_version_manager()
    
    def save_device_labels(
        self,
        device_id: str,
        new_labels: List[dict],
        username: str,
        change_summary: str = '',
        protocol_meta: dict = None,
        base_commit: str = None,
        base_version: str = None,
        db_save_func=None
    ) -> Tuple[bool, str, dict]:
        """保存设备 Labels
        
        Args:
            device_id: 设备 ID
            new_labels: 新的 Labels 列表
            username: 操作用户名
            change_summary: 变更说明
            protocol_meta: 协议元信息
            base_commit: 基准 commit（用于乐观锁）
            base_version: 基准版本号
            db_save_func: 数据库保存函数（用于双写）
        
        Returns:
            (success, message, result_data)
        """
        result_data = {}
        
        # 1. 先保存到数据库（如果提供了保存函数）
        if db_save_func:
            try:
                db_result = db_save_func()
                if isinstance(db_result, tuple):
                    db_success, db_data = db_result[0], db_result[1] if len(db_result) > 1 else {}
                else:
                    db_success, db_data = db_result, {}
                
                if not db_success:
                    return False, '数据库保存失败', db_data
                
                result_data.update(db_data if isinstance(db_data, dict) else {})
            except Exception as e:
                return False, f'数据库保存失败: {str(e)}', {}
        
        # 2. 如果启用了 Git 存储，同时保存到 Git
        if is_git_storage_enabled():
            try:
                git_success, git_msg, git_data = self.version_manager.save_device_version(
                    device_id=device_id,
                    new_labels=new_labels,
                    username=username,
                    change_summary=change_summary,
                    protocol_meta=protocol_meta,
                    base_commit=base_commit,
                    base_version=base_version
                )
                
                if git_success:
                    # 合并 Git 返回的数据
                    result_data['git_commit'] = git_data.get('new_commit', '')
                    result_data['git_version'] = git_data.get('new_version', '')
                else:
                    # Git 保存失败，记录但不影响主流程
                    print(f'Git 保存失败（不影响数据库）: {git_msg}')
                    result_data['git_error'] = git_msg
                    
            except Exception as e:
                print(f'Git 保存异常（不影响数据库）: {str(e)}')
                result_data['git_error'] = str(e)
        
        return True, '保存成功', result_data
    
    def get_device_info_with_git(self, device_id: str) -> Optional[dict]:
        """获取设备信息（包含 Git 信息）
        
        如果启用了 Git 存储，会尝试从 Git 获取额外信息
        """
        if not is_git_storage_enabled():
            return None
        
        return self.version_manager.get_device_info(device_id)
    
    def get_version_history_from_git(self, device_id: str, limit: int = 20) -> List[dict]:
        """从 Git 获取版本历史
        
        如果启用了 Git 存储，返回 Git 中的版本历史
        """
        if not is_git_storage_enabled():
            return []
        
        return self.version_manager.get_device_version_history(device_id, limit)


# 全局单例
_save_adapter: Optional[SaveAdapter] = None


def get_save_adapter() -> SaveAdapter:
    """获取全局 SaveAdapter 实例"""
    global _save_adapter
    if _save_adapter is None:
        _save_adapter = SaveAdapter()
    return _save_adapter
