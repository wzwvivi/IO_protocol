# -*- coding: utf-8 -*-
"""
Git 存储模块
按 ATA 系统分 repo 管理协议版本
"""

from .config import GitStorageConfig
from .repo_manager import ATARepoManager, get_repo_manager
from .device_storage import DeviceStorage, get_device_storage
from .version_manager import VersionManager, get_version_manager
from .lock_manager import DeviceLockManager, get_lock_manager
from .save_adapter import SaveAdapter, get_save_adapter, is_git_storage_enabled, enable_git_storage, disable_git_storage
from .read_adapter import ReadAdapter, get_read_adapter

__all__ = [
    'GitStorageConfig',
    'ATARepoManager',
    'get_repo_manager',
    'DeviceStorage',
    'get_device_storage',
    'VersionManager',
    'get_version_manager',
    'DeviceLockManager',
    'get_lock_manager',
    'SaveAdapter',
    'get_save_adapter',
    'is_git_storage_enabled',
    'enable_git_storage',
    'disable_git_storage',
    'ReadAdapter',
    'get_read_adapter'
]
