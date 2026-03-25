# -*- coding: utf-8 -*-
"""
ATA Repo 管理器
负责 ATA 级 Git 仓库的创建、初始化和基本操作
"""

import os
import json
import subprocess
import threading
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from queue import Queue
import time

from .config import (
    GitStorageConfig, RepoMeta, 
    REPO_META_FILE, DEVICES_DIR,
    extract_ata_code, get_ata_info, ATA_SYSTEMS
)


class ATARepoManager:
    """ATA 仓库管理器"""
    
    def __init__(self, config: Optional[GitStorageConfig] = None):
        self.config = config or GitStorageConfig()
        
        # ATA 级写队列 - 每个 ATA 一个队列
        self._write_queues: Dict[str, Queue] = {}
        self._write_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
    
    def _get_write_lock(self, ata_code: str) -> threading.Lock:
        """获取 ATA 级写锁"""
        ata_code = ata_code.lower()
        with self._global_lock:
            if ata_code not in self._write_locks:
                self._write_locks[ata_code] = threading.Lock()
            return self._write_locks[ata_code]
    
    def ensure_repos_root(self) -> str:
        """确保仓库根目录存在"""
        os.makedirs(self.config.repos_root, exist_ok=True)
        return self.config.repos_root
    
    def list_ata_repos(self) -> List[str]:
        """列出所有 ATA 仓库"""
        self.ensure_repos_root()
        repos = []
        for name in os.listdir(self.config.repos_root):
            if name.startswith('protocol-ata'):
                repo_path = os.path.join(self.config.repos_root, name)
                if os.path.isdir(repo_path):
                    ata_code = name.replace('protocol-', '')
                    repos.append(ata_code)
        return repos
    
    def repo_exists(self, ata_code: str) -> bool:
        """检查 ATA 仓库是否存在"""
        repo_path = self.config.get_ata_repo_path(ata_code)
        return os.path.exists(repo_path) and os.path.isdir(repo_path)
    
    def is_git_repo(self, ata_code: str) -> bool:
        """检查是否是有效的 Git 仓库"""
        repo_path = self.config.get_ata_repo_path(ata_code)
        git_dir = os.path.join(repo_path, '.git')
        return os.path.exists(git_dir)
    
    def init_repo(self, ata_code: str, ata_name: Optional[str] = None) -> Tuple[bool, str]:
        """初始化 ATA 仓库
        
        Args:
            ata_code: ATA 代码，如 'ata32'
            ata_name: ATA 名称，如 '起落架系统'，如果不提供则从 ATA_SYSTEMS 查找
        
        Returns:
            (success, message)
        """
        ata_code = ata_code.lower()
        
        # 获取 ATA 信息
        ata_info = get_ata_info(ata_code)
        if ata_name is None:
            ata_name = ata_info['name'] if ata_info else f'{ata_code.upper()} 系统'
        
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        # 创建目录结构
        os.makedirs(repo_path, exist_ok=True)
        devices_dir = os.path.join(repo_path, DEVICES_DIR)
        os.makedirs(devices_dir, exist_ok=True)
        
        # 创建 repo_meta.json
        repo_meta = RepoMeta(
            ata_code=ata_code.upper(),
            ata_name=ata_name,
            created_at=datetime.now().isoformat()
        )
        meta_path = os.path.join(repo_path, REPO_META_FILE)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(repo_meta.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 初始化 Git 仓库
        if not self.is_git_repo(ata_code):
            try:
                self._run_git_command(repo_path, ['init'])
                
                # 配置 Git
                self._run_git_command(repo_path, ['config', 'user.name', self.config.git_author_name])
                self._run_git_command(repo_path, ['config', 'user.email', self.config.git_author_email])
                
                # 创建 .gitignore
                gitignore_path = os.path.join(repo_path, '.gitignore')
                with open(gitignore_path, 'w', encoding='utf-8') as f:
                    f.write('# 忽略临时文件\n')
                    f.write('*.tmp\n')
                    f.write('*.bak\n')
                    f.write('.DS_Store\n')
                    f.write('__pycache__/\n')
                
                # 初始提交
                self._run_git_command(repo_path, ['add', '.'])
                self._run_git_command(repo_path, ['commit', '-m', f'初始化 {ata_code.upper()} 协议仓库'])
                
                return True, f'ATA 仓库 {ata_code} 初始化成功'
            except Exception as e:
                return False, f'Git 初始化失败: {str(e)}'
        
        return True, f'ATA 仓库 {ata_code} 已存在'
    
    def get_repo_meta(self, ata_code: str) -> Optional[RepoMeta]:
        """获取仓库元数据"""
        repo_path = self.config.get_ata_repo_path(ata_code)
        meta_path = os.path.join(repo_path, REPO_META_FILE)
        
        if not os.path.exists(meta_path):
            return None
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return RepoMeta.from_dict(data)
        except Exception:
            return None
    
    def _run_git_command(self, repo_path: str, args: List[str], 
                         capture_output: bool = True) -> Tuple[int, str, str]:
        """执行 Git 命令
        
        Args:
            repo_path: 仓库路径
            args: Git 命令参数
            capture_output: 是否捕获输出
        
        Returns:
            (return_code, stdout, stderr)
        """
        cmd = ['git'] + args
        
        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=capture_output,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, '', str(e)
    
    def git_add(self, ata_code: str, paths: List[str] = None) -> Tuple[bool, str]:
        """Git add 操作
        
        Args:
            ata_code: ATA 代码
            paths: 要添加的路径列表，None 表示添加所有
        
        Returns:
            (success, message)
        """
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        if paths:
            args = ['add'] + paths
        else:
            args = ['add', '.']
        
        code, stdout, stderr = self._run_git_command(repo_path, args)
        
        if code == 0:
            return True, 'Git add 成功'
        else:
            return False, f'Git add 失败: {stderr}'
    
    def git_commit(self, ata_code: str, message: str, 
                   author: Optional[str] = None) -> Tuple[bool, str, str]:
        """Git commit 操作
        
        Args:
            ata_code: ATA 代码
            message: 提交信息
            author: 作者，格式 'Name <email>'
        
        Returns:
            (success, message, commit_hash)
        """
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        args = ['commit', '-m', message]
        if author:
            args.extend(['--author', author])
        
        code, stdout, stderr = self._run_git_command(repo_path, args)
        
        if code == 0:
            # 获取 commit hash
            code2, hash_out, _ = self._run_git_command(repo_path, ['rev-parse', 'HEAD'])
            commit_hash = hash_out.strip() if code2 == 0 else ''
            return True, 'Git commit 成功', commit_hash
        elif 'nothing to commit' in stderr or 'nothing to commit' in stdout:
            return True, '没有需要提交的更改', ''
        else:
            return False, f'Git commit 失败: {stderr}', ''
    
    def git_tag(self, ata_code: str, tag_name: str, 
                message: Optional[str] = None) -> Tuple[bool, str]:
        """Git tag 操作
        
        Args:
            ata_code: ATA 代码
            tag_name: 标签名称
            message: 标签说明
        
        Returns:
            (success, message)
        """
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        if message:
            args = ['tag', '-a', tag_name, '-m', message]
        else:
            args = ['tag', tag_name]
        
        code, stdout, stderr = self._run_git_command(repo_path, args)
        
        if code == 0:
            return True, f'Git tag {tag_name} 创建成功'
        elif 'already exists' in stderr:
            return True, f'Git tag {tag_name} 已存在'
        else:
            return False, f'Git tag 失败: {stderr}'
    
    def get_current_commit(self, ata_code: str) -> Optional[str]:
        """获取当前 commit hash"""
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        if not self.is_git_repo(ata_code):
            return None
        
        code, stdout, stderr = self._run_git_command(repo_path, ['rev-parse', 'HEAD'])
        
        if code == 0:
            return stdout.strip()
        return None
    
    def get_file_last_commit(self, ata_code: str, file_path: str) -> Optional[str]:
        """获取文件最后一次提交的 commit hash
        
        Args:
            ata_code: ATA 代码
            file_path: 相对于仓库根目录的文件路径
        
        Returns:
            commit hash 或 None
        """
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        if not self.is_git_repo(ata_code):
            return None
        
        code, stdout, stderr = self._run_git_command(
            repo_path, 
            ['log', '-1', '--format=%H', '--', file_path]
        )
        
        if code == 0 and stdout.strip():
            return stdout.strip()
        return None
    
    def get_device_last_commit(self, ata_code: str, device_id: str) -> Optional[str]:
        """获取设备目录最后一次提交的 commit hash"""
        device_rel_path = f'{DEVICES_DIR}/{device_id}'
        return self.get_file_last_commit(ata_code, device_rel_path)
    
    def list_tags(self, ata_code: str, pattern: Optional[str] = None) -> List[str]:
        """列出标签
        
        Args:
            ata_code: ATA 代码
            pattern: 标签名称模式，如 'ata32_32_3-*'
        
        Returns:
            标签列表
        """
        repo_path = self.config.get_ata_repo_path(ata_code)
        
        if not self.is_git_repo(ata_code):
            return []
        
        args = ['tag', '-l']
        if pattern:
            args.append(pattern)
        
        code, stdout, stderr = self._run_git_command(repo_path, args)
        
        if code == 0:
            return [t.strip() for t in stdout.strip().split('\n') if t.strip()]
        return []
    
    def get_device_tags(self, ata_code: str, device_id: str) -> List[str]:
        """获取设备的所有标签"""
        pattern = f'{device_id}-*'
        return self.list_tags(ata_code, pattern)
    
    def with_write_lock(self, ata_code: str):
        """获取 ATA 级写锁的上下文管理器
        
        用法:
            with repo_manager.with_write_lock('ata32'):
                # 执行写操作
        """
        return _ATAWriteLockContext(self, ata_code)
    
    def acquire_write_lock(self, ata_code: str, timeout: Optional[float] = None) -> bool:
        """获取 ATA 级写锁
        
        Args:
            ata_code: ATA 代码
            timeout: 超时时间（秒），None 表示使用默认配置
        
        Returns:
            是否成功获取锁
        """
        if timeout is None:
            timeout = self.config.write_queue_timeout_seconds
        
        lock = self._get_write_lock(ata_code)
        return lock.acquire(timeout=timeout)
    
    def release_write_lock(self, ata_code: str):
        """释放 ATA 级写锁"""
        lock = self._get_write_lock(ata_code)
        try:
            lock.release()
        except RuntimeError:
            pass  # 锁未被持有


class _ATAWriteLockContext:
    """ATA 写锁上下文管理器"""
    
    def __init__(self, manager: ATARepoManager, ata_code: str):
        self.manager = manager
        self.ata_code = ata_code
        self.acquired = False
    
    def __enter__(self):
        self.acquired = self.manager.acquire_write_lock(self.ata_code)
        if not self.acquired:
            raise TimeoutError(f'获取 {self.ata_code} 写锁超时')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            self.manager.release_write_lock(self.ata_code)
        return False


# 全局单例
_repo_manager: Optional[ATARepoManager] = None


def get_repo_manager() -> ATARepoManager:
    """获取全局 ATARepoManager 实例"""
    global _repo_manager
    if _repo_manager is None:
        _repo_manager = ATARepoManager()
    return _repo_manager
