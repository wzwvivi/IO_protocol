# -*- coding: utf-8 -*-
"""
设备编辑锁管理器
实现设备级软锁/租约锁，支持心跳续租和超时自动释放
"""

import uuid
import threading
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .config import GitStorageConfig


@dataclass
class DeviceLock:
    """设备锁信息"""
    device_id: str
    session_id: str
    locked_by: str  # 用户名
    locked_by_display_name: str
    lock_acquired_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime
    is_active: bool = True
    
    def to_dict(self) -> dict:
        return {
            'device_id': self.device_id,
            'session_id': self.session_id,
            'locked_by': self.locked_by,
            'locked_by_display_name': self.locked_by_display_name,
            'lock_acquired_at': self.lock_acquired_at.isoformat(),
            'last_heartbeat_at': self.last_heartbeat_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_active': self.is_active
        }
    
    def is_expired(self) -> bool:
        """检查锁是否已过期"""
        return datetime.now() > self.expires_at


class DeviceLockManager:
    """设备编辑锁管理器
    
    实现设备级软锁：
    - 同一设备同一时刻只能有一个人编辑
    - 锁有超时时间，需要心跳续租
    - 浏览器关闭/断网后超时自动释放
    """
    
    def __init__(self, config: Optional[GitStorageConfig] = None):
        self.config = config or GitStorageConfig()
        
        # 内存锁存储（生产环境应该用数据库）
        self._locks: Dict[str, DeviceLock] = {}
        self._lock = threading.Lock()
    
    def acquire_lock(
        self,
        device_id: str,
        username: str,
        display_name: str = '',
        session_id: str = None
    ) -> Tuple[bool, str, Optional[dict]]:
        """申请设备编辑锁
        
        Args:
            device_id: 设备 ID
            username: 用户名
            display_name: 显示名称
            session_id: 会话 ID，如果不提供则自动生成
        
        Returns:
            (success, message, lock_info)
            - success: 是否成功获取锁
            - message: 结果消息
            - lock_info: 锁信息（成功时返回自己的锁，失败时返回当前持有者的锁）
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        with self._lock:
            # 清理过期锁
            self._cleanup_expired_locks()
            
            # 检查是否已有锁
            existing_lock = self._locks.get(device_id)
            
            if existing_lock and existing_lock.is_active:
                # 如果是同一用户同一会话，续租
                if existing_lock.locked_by == username and existing_lock.session_id == session_id:
                    existing_lock.last_heartbeat_at = datetime.now()
                    existing_lock.expires_at = datetime.now() + timedelta(
                        seconds=self.config.lock_timeout_seconds
                    )
                    return True, '锁续租成功', existing_lock.to_dict()
                
                # 如果是同一用户不同会话，允许接管
                if existing_lock.locked_by == username:
                    existing_lock.session_id = session_id
                    existing_lock.last_heartbeat_at = datetime.now()
                    existing_lock.expires_at = datetime.now() + timedelta(
                        seconds=self.config.lock_timeout_seconds
                    )
                    return True, '锁接管成功', existing_lock.to_dict()
                
                # 被其他用户持有
                return False, f'设备正由 {existing_lock.locked_by_display_name or existing_lock.locked_by} 编辑中', existing_lock.to_dict()
            
            # 创建新锁
            now = datetime.now()
            new_lock = DeviceLock(
                device_id=device_id,
                session_id=session_id,
                locked_by=username,
                locked_by_display_name=display_name or username,
                lock_acquired_at=now,
                last_heartbeat_at=now,
                expires_at=now + timedelta(seconds=self.config.lock_timeout_seconds),
                is_active=True
            )
            
            self._locks[device_id] = new_lock
            return True, '获取锁成功', new_lock.to_dict()
    
    def release_lock(
        self,
        device_id: str,
        username: str,
        session_id: str = None
    ) -> Tuple[bool, str]:
        """释放设备编辑锁
        
        Args:
            device_id: 设备 ID
            username: 用户名
            session_id: 会话 ID（可选，用于验证）
        
        Returns:
            (success, message)
        """
        with self._lock:
            existing_lock = self._locks.get(device_id)
            
            if not existing_lock:
                return True, '锁不存在或已释放'
            
            # 验证是否是锁持有者
            if existing_lock.locked_by != username:
                return False, '无权释放他人的锁'
            
            # 如果提供了 session_id，验证会话
            if session_id and existing_lock.session_id != session_id:
                return False, '会话不匹配'
            
            # 释放锁
            del self._locks[device_id]
            return True, '锁已释放'
    
    def heartbeat(
        self,
        device_id: str,
        username: str,
        session_id: str
    ) -> Tuple[bool, str, Optional[dict]]:
        """心跳续租
        
        Args:
            device_id: 设备 ID
            username: 用户名
            session_id: 会话 ID
        
        Returns:
            (success, message, lock_info)
        """
        with self._lock:
            existing_lock = self._locks.get(device_id)
            
            if not existing_lock:
                return False, '锁不存在，请重新获取', None
            
            if existing_lock.locked_by != username:
                return False, '锁已被他人持有', existing_lock.to_dict()
            
            if existing_lock.session_id != session_id:
                return False, '会话不匹配，锁可能已被接管', existing_lock.to_dict()
            
            if existing_lock.is_expired():
                del self._locks[device_id]
                return False, '锁已过期，请重新获取', None
            
            # 续租
            existing_lock.last_heartbeat_at = datetime.now()
            existing_lock.expires_at = datetime.now() + timedelta(
                seconds=self.config.lock_timeout_seconds
            )
            
            return True, '心跳成功', existing_lock.to_dict()
    
    def get_lock_status(self, device_id: str) -> dict:
        """获取设备锁状态
        
        Returns:
            {
                'is_locked': bool,
                'locked_by': str or None,
                'locked_by_display_name': str or None,
                'lock_acquired_at': str or None,
                'expires_at': str or None
            }
        """
        with self._lock:
            self._cleanup_expired_locks()
            
            existing_lock = self._locks.get(device_id)
            
            if not existing_lock or not existing_lock.is_active:
                return {
                    'is_locked': False,
                    'locked_by': None,
                    'locked_by_display_name': None,
                    'lock_acquired_at': None,
                    'expires_at': None
                }
            
            return {
                'is_locked': True,
                'locked_by': existing_lock.locked_by,
                'locked_by_display_name': existing_lock.locked_by_display_name,
                'lock_acquired_at': existing_lock.lock_acquired_at.isoformat(),
                'expires_at': existing_lock.expires_at.isoformat()
            }
    
    def get_lock_info_for_user(self, device_id: str, username: str) -> dict:
        """获取设备锁状态（包含是否是自己持有）
        
        Returns:
            {
                'lock_status': 'free' | 'locked_by_self' | 'locked_by_other',
                'lock_info': {...} or None,
                'can_edit': bool
            }
        """
        with self._lock:
            self._cleanup_expired_locks()
            
            existing_lock = self._locks.get(device_id)
            
            if not existing_lock or not existing_lock.is_active:
                return {
                    'lock_status': 'free',
                    'lock_info': None,
                    'can_edit': True
                }
            
            if existing_lock.locked_by == username:
                return {
                    'lock_status': 'locked_by_self',
                    'lock_info': existing_lock.to_dict(),
                    'can_edit': True
                }
            
            return {
                'lock_status': 'locked_by_other',
                'lock_info': existing_lock.to_dict(),
                'can_edit': False
            }
    
    def get_all_locks(self) -> Dict[str, dict]:
        """获取所有活跃的锁（用于设备树展示）"""
        with self._lock:
            self._cleanup_expired_locks()
            
            return {
                device_id: lock.to_dict()
                for device_id, lock in self._locks.items()
                if lock.is_active
            }
    
    def get_devices_lock_status(self, device_ids: list, username: str = None) -> Dict[str, dict]:
        """批量获取设备锁状态
        
        Args:
            device_ids: 设备 ID 列表
            username: 当前用户名（用于判断是否是自己持有）
        
        Returns:
            {
                device_id: {
                    'is_locked': bool,
                    'locked_by': str or None,
                    'locked_by_display_name': str or None,
                    'locked_by_self': bool
                }
            }
        """
        with self._lock:
            self._cleanup_expired_locks()
            
            result = {}
            for device_id in device_ids:
                existing_lock = self._locks.get(device_id)
                
                if not existing_lock or not existing_lock.is_active:
                    result[device_id] = {
                        'is_locked': False,
                        'locked_by': None,
                        'locked_by_display_name': None,
                        'locked_by_self': False
                    }
                else:
                    result[device_id] = {
                        'is_locked': True,
                        'locked_by': existing_lock.locked_by,
                        'locked_by_display_name': existing_lock.locked_by_display_name,
                        'locked_by_self': username and existing_lock.locked_by == username
                    }
            
            return result
    
    def _cleanup_expired_locks(self):
        """清理过期的锁（内部方法，需要在持有 _lock 时调用）"""
        expired_devices = [
            device_id
            for device_id, lock in self._locks.items()
            if lock.is_expired()
        ]
        
        for device_id in expired_devices:
            del self._locks[device_id]
    
    def force_release_lock(self, device_id: str, admin_username: str) -> Tuple[bool, str]:
        """强制释放锁（管理员操作）
        
        Args:
            device_id: 设备 ID
            admin_username: 管理员用户名
        
        Returns:
            (success, message)
        """
        with self._lock:
            existing_lock = self._locks.get(device_id)
            
            if not existing_lock:
                return True, '锁不存在'
            
            original_holder = existing_lock.locked_by
            del self._locks[device_id]
            
            return True, f'已强制释放 {original_holder} 持有的锁'


# 全局单例
_lock_manager: Optional[DeviceLockManager] = None


def get_lock_manager() -> DeviceLockManager:
    """获取全局 DeviceLockManager 实例"""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = DeviceLockManager()
    return _lock_manager
