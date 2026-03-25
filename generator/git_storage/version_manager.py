# -*- coding: utf-8 -*-
"""
版本管理器
负责设备版本的创建、保存和历史管理
"""

import re
import json
import copy
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from .config import (
    GitStorageConfig, DeviceMeta, ReleaseRecord, ChangeStats, SaveRecord,
    extract_ata_code, generate_release_id, generate_git_tag, generate_save_id
)
from .repo_manager import ATARepoManager, get_repo_manager
from .device_storage import DeviceStorage, get_device_storage


class VersionManager:
    """版本管理器"""
    
    def __init__(self, config: Optional[GitStorageConfig] = None,
                 repo_manager: Optional[ATARepoManager] = None,
                 device_storage: Optional[DeviceStorage] = None):
        self.config = config or GitStorageConfig()
        self.repo_manager = repo_manager or get_repo_manager()
        self.device_storage = device_storage or get_device_storage()
    
    @staticmethod
    def increment_version(version_str: str) -> str:
        """版本号主版本升级
        
        Args:
            version_str: 当前版本号，如 'V5.0'
        
        Returns:
            新版本号，如 'V6.0'
        """
        match = re.match(r'([Vv]?)(\d+)\.?(\d*)', version_str)
        if not match:
            return 'V2.0'
        
        prefix = match.group(1) or 'V'
        major = int(match.group(2))
        major += 1
        
        return f'{prefix}{major}.0'
    
    @staticmethod
    def compute_labels_diff(old_labels: List[dict], new_labels: List[dict]) -> dict:
        """计算两个 labels 列表的差异
        
        Returns:
            {
                'added': [...],
                'added_details': [...],
                'removed': [...],
                'removed_details': [...],
                'modified': [...],
                'modified_details': [...]
            }
        """
        old_map = {label.get('label_oct', ''): label for label in old_labels if label.get('label_oct')}
        new_map = {label.get('label_oct', ''): label for label in new_labels if label.get('label_oct')}
        
        old_octs = set(old_map.keys())
        new_octs = set(new_map.keys())
        
        # 新增的 Labels
        added_details = []
        for oct_val in sorted(new_octs - old_octs):
            label = new_map[oct_val]
            added_details.append({
                'label_oct': oct_val,
                'name': label.get('name', ''),
                'direction': label.get('direction', '')
            })
        
        # 删除的 Labels
        removed_details = []
        for oct_val in sorted(old_octs - new_octs):
            label = old_map[oct_val]
            removed_details.append({
                'label_oct': oct_val,
                'name': label.get('name', ''),
                'direction': label.get('direction', '')
            })
        
        # 修改的 Labels
        modified_details = []
        for oct_val in sorted(old_octs & new_octs):
            old_label = old_map[oct_val]
            new_label = new_map[oct_val]
            
            if json.dumps(old_label, sort_keys=True) != json.dumps(new_label, sort_keys=True):
                modified_details.append({
                    'label_oct': oct_val,
                    'name': new_label.get('name', old_label.get('name', '')),
                    'old_name': old_label.get('name', ''),
                    'new_name': new_label.get('name', '')
                })
        
        return {
            'added': [d['label_oct'] for d in added_details],
            'added_details': added_details,
            'removed': [d['label_oct'] for d in removed_details],
            'removed_details': removed_details,
            'modified': [d['label_oct'] for d in modified_details],
            'modified_details': modified_details
        }
    
    @staticmethod
    def has_labels_changed(old_labels: List[dict], new_labels: List[dict]) -> bool:
        """检查 labels 是否有变化"""
        diff = VersionManager.compute_labels_diff(old_labels, new_labels)
        return bool(diff['added'] or diff['removed'] or diff['modified'])
    
    def save_device_version(
        self,
        device_id: str,
        new_labels: List[dict],
        username: str,
        change_summary: str = '',
        protocol_meta: dict = None,
        base_commit: str = None,
        base_version: str = None
    ) -> Tuple[bool, str, dict]:
        """保存设备版本
        
        这是核心保存方法，实现：
        1. 设备级乐观锁检查
        2. ATA 级写队列
        3. Git 提交和 tag
        4. 版本快照和发布记录
        
        Args:
            device_id: 设备 ID
            new_labels: 新的 Labels 列表
            username: 操作用户名
            change_summary: 变更说明
            protocol_meta: 协议元信息
            base_commit: 基准 commit（用于乐观锁）
            base_version: 基准版本号
        
        Returns:
            (success, message, result_data)
            result_data 包含:
            - new_version: 新版本号
            - new_commit: 新 commit hash
            - change_stats: 变更统计
            - saved_at: 保存时间
            - saved_by: 保存人
        """
        # 提取 ATA 代码
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return False, f'无法从 device_id 提取 ATA 代码: {device_id}', {}
        
        # 确保 ATA 仓库存在
        if not self.repo_manager.repo_exists(ata_code):
            success, msg = self.repo_manager.init_repo(ata_code)
            if not success:
                return False, msg, {}
        
        # 获取 ATA 级写锁
        try:
            with self.repo_manager.with_write_lock(ata_code):
                return self._do_save_device_version(
                    ata_code, device_id, new_labels, username,
                    change_summary, protocol_meta, base_commit, base_version
                )
        except TimeoutError:
            return False, f'获取 {ata_code} 写锁超时，请稍后重试', {
                'error_type': 'repo_busy'
            }
    
    def _do_save_device_version(
        self,
        ata_code: str,
        device_id: str,
        new_labels: List[dict],
        username: str,
        change_summary: str,
        protocol_meta: dict,
        base_commit: str,
        base_version: str
    ) -> Tuple[bool, str, dict]:
        """实际执行保存操作（在写锁内）
        
        重构后的事务顺序：
        1. 乐观锁检查
        2. 计算差异和版本号
        3. 写入所有文件（current/、versions/、history/）
        4. 统一 git add + commit
        5. 打 tag
        6. 更新 commit hash 到 meta（二次提交）
        
        这样保证一次保存的所有产物（快照、历史索引）都在同一个 commit 中。
        """
        saved_at = datetime.now().isoformat()
        
        # ========== 阶段1: 检查与准备 ==========
        
        # 1.1 乐观锁检查
        if base_commit:
            current_commit = self.device_storage.get_device_base_commit(ata_code, device_id)
            if current_commit and current_commit != base_commit:
                device_meta = self.device_storage.get_device_meta(ata_code, device_id)
                return False, '设备已被他人更新，请先查看最新版本', {
                    'error_type': 'conflict',
                    'latest_commit': current_commit,
                    'latest_version': device_meta.current_version if device_meta else '',
                    'latest_updated_by': device_meta.updated_by if device_meta else ''
                }
        
        # 1.2 获取或初始化设备
        device_meta = self.device_storage.get_device_meta(ata_code, device_id)
        if not device_meta:
            success, msg = self.device_storage.init_device(
                ata_code, device_id, device_id,
                description=''
            )
            if not success:
                return False, msg, {}
            device_meta = self.device_storage.get_device_meta(ata_code, device_id)
        
        # 1.3 获取旧 Labels 并计算差异
        old_labels = self.device_storage.get_labels(ata_code, device_id)
        diff = self.compute_labels_diff(old_labels, new_labels)
        has_changed = bool(diff['added'] or diff['removed'] or diff['modified'])
        
        # 1.4 确定版本号
        current_version = device_meta.current_version
        if has_changed:
            new_version = self.increment_version(current_version)
        else:
            new_version = current_version
        
        # 1.5 生成变更说明
        if not change_summary and has_changed:
            parts = []
            if diff['added']:
                parts.append(f"新增 {len(diff['added'])} 个 Label")
            if diff['removed']:
                parts.append(f"删除 {len(diff['removed'])} 个 Label")
            if diff['modified']:
                parts.append(f"修改 {len(diff['modified'])} 个 Label")
            change_summary = '；'.join(parts) if parts else '无变更'
        elif not change_summary:
            change_summary = '无变更'
        
        # ========== 阶段2: 写入所有文件（在 git commit 之前） ==========
        
        # 2.1 保存 Labels 到 current/labels/
        self.device_storage.save_labels(ata_code, device_id, new_labels, split_files=True)
        
        # 2.2 保存当前协议到 current/protocol.json
        self.device_storage.save_current_protocol(
            ata_code, device_id,
            protocol_meta or {},
            new_labels,
            {
                'version': new_version,
                'created_at': saved_at,
                'created_by': username
            }
        )
        
        # 2.3 更新设备元数据（暂不写 commit hash，等 git commit 后再更新）
        device_meta.current_version = new_version
        device_meta.updated_at = saved_at
        device_meta.updated_by = username
        self.device_storage.save_device_meta(ata_code, device_id, device_meta)
        
        # 2.4 保存版本快照到 versions/<version>.json
        if has_changed:
            snapshot = {
                'version': new_version,
                'created_at': saved_at,
                'created_by': username,
                'protocol_meta': protocol_meta or {},
                'labels': new_labels,
                'label_count': len(new_labels),
                'from_version': current_version
            }
            self.device_storage.save_version_snapshot(ata_code, device_id, new_version, snapshot)
        
        # 2.5 构建变更统计
        change_stats = ChangeStats(
            added=len(diff['added']),
            modified=len(diff['modified']),
            deleted=len(diff['removed'])
        )
        
        diff_details = {
            'added_details': diff['added_details'],
            'removed_details': diff['removed_details'],
            'modified_details': diff['modified_details']
        }
        
        # 2.6 生成保存记录 ID 和发布记录 ID
        save_id = generate_save_id(device_id, saved_at.replace('-', '').replace(':', '').replace('T', ''))
        release_id = generate_release_id(device_id, new_version) if has_changed else ''
        
        # 2.7 添加保存记录到 history/saves.json（每次保存都记录）
        save_record = SaveRecord(
            save_id=save_id,
            device_id=device_id,
            version=new_version,
            summary=change_summary,
            change_stats=change_stats,
            diff_details=diff_details,
            git_commit='',  # 先留空，commit 后更新
            has_changed=has_changed,
            is_release=has_changed,  # 有变更时才是正式发布
            release_id=release_id,
            created_by=username,
            created_at=saved_at,
            label_count=len(new_labels)
        )
        self.device_storage.add_save(ata_code, device_id, save_record)
        
        # 2.8 添加发布记录到 history/releases.json（仅当有变更时）
        if has_changed:
            release = ReleaseRecord(
                release_id=release_id,
                device_id=device_id,
                from_version=current_version,
                to_version=new_version,
                summary=change_summary,
                change_stats=change_stats,
                git_commit='',  # 先留空，commit 后更新
                git_tag=generate_git_tag(device_id, new_version),
                created_by=username,
                created_at=saved_at,
                diff_details=diff_details,
                label_count=len(new_labels)  # 记录该版本的 label 数量
            )
            self.device_storage.add_release(ata_code, device_id, release)
        
        # ========== 阶段3: Git 提交（一次性提交所有变更） ==========
        
        commit_message = f'{device_id}: {change_summary}'
        self.repo_manager.git_add(ata_code)
        success, msg, commit_hash = self.repo_manager.git_commit(ata_code, commit_message)
        
        if not success and 'nothing to commit' not in msg:
            return False, f'Git 提交失败: {msg}', {}
        
        # ========== 阶段4: 打 tag ==========
        
        if has_changed and commit_hash:
            tag_name = generate_git_tag(device_id, new_version)
            self.repo_manager.git_tag(ata_code, tag_name, change_summary)
        
        # ========== 阶段5: 回填 commit hash 到历史记录 ==========
        # 
        # 简化方案：不再做二次提交，直接用主提交的 commit hash
        # 这样避免了"脏写"问题，保证 Git 状态干净
        # 
        # 乐观锁基准使用主提交的 commit hash，足够保证并发安全
        
        final_commit = commit_hash
        if commit_hash:
            # 更新设备元数据的 commit（内存中）
            device_meta.current_commit = commit_hash
            
            # 回填 commit hash 到 saves.json 和 releases.json（仅更新内存/文件，不再 commit）
            # 这些文件会在下次保存时一起提交，或者可以接受轻微的不一致
            # 因为乐观锁检查是基于 Git 历史，不是基于文件内容
            self.device_storage.update_latest_save_commit(ata_code, device_id, commit_hash)
            if has_changed:
                self.device_storage.update_latest_release_commit(ata_code, device_id, commit_hash)
            
            # 更新 device_meta 文件
            self.device_storage.save_device_meta(ata_code, device_id, device_meta)
            
            # 补提交：把 commit hash 回填的改动也提交进去，保证工作区干净
            self.repo_manager.git_add(ata_code)
            self.repo_manager.git_commit(ata_code, f'{device_id}: finalize commit hash')
        
        # ========== 阶段6: 返回结果 ==========
        
        return True, '保存成功', {
            'new_version': new_version,
            'old_version': current_version,
            'new_commit': final_commit or '',
            'save_id': save_id,
            'release_id': release_id,
            'change_stats': {
                'added': len(diff['added']),
                'modified': len(diff['modified']),
                'deleted': len(diff['removed'])
            },
            'diff_details': diff_details,
            'change_summary': change_summary,
            'saved_at': saved_at,
            'saved_by': username,
            'has_changed': has_changed,
            'is_release': has_changed,
            'label_count': len(new_labels)
        }
    
    def get_device_version_history(self, device_id: str, limit: int = 20) -> List[dict]:
        """获取设备发布历史（正式版本节点）
        
        Args:
            device_id: 设备 ID
            limit: 返回记录数限制
        
        Returns:
            发布历史列表
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return []
        
        releases = self.device_storage.get_releases(ata_code, device_id)
        
        history = []
        for release in releases[:limit]:
            # 如果 release 没有 label_count，尝试从版本快照获取
            label_count = release.label_count if hasattr(release, 'label_count') and release.label_count > 0 else 0
            if label_count == 0:
                # 尝试从版本快照获取 label_count
                snapshot = self.device_storage.get_version_snapshot(ata_code, device_id, release.to_version)
                if snapshot:
                    label_count = snapshot.get('label_count', len(snapshot.get('labels', [])))
            
            history.append({
                'release_id': release.release_id,
                'version': release.to_version,
                'from_version': release.from_version,
                'updated_at': release.created_at,
                'updated_by': release.created_by,
                'change_summary': release.summary,
                'change_stats': release.change_stats.to_dict() if isinstance(release.change_stats, ChangeStats) else release.change_stats,
                'diff_details': release.diff_details,
                'git_commit': release.git_commit,
                'git_tag': release.git_tag,
                'is_release': True,
                'label_count': label_count
            })
        
        return history
    
    def get_device_save_history(self, device_id: str, limit: int = 50) -> List[dict]:
        """获取设备保存历史（完整保存时间线）
        
        Args:
            device_id: 设备 ID
            limit: 返回记录数限制
        
        Returns:
            保存历史列表
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return []
        
        saves = self.device_storage.get_saves(ata_code, device_id)
        
        history = []
        for save in saves[:limit]:
            history.append({
                'save_id': save.save_id,
                'version': save.version,
                'updated_at': save.created_at,
                'updated_by': save.created_by,
                'change_summary': save.summary,
                'change_stats': save.change_stats.to_dict() if isinstance(save.change_stats, ChangeStats) else save.change_stats,
                'diff_details': save.diff_details,
                'git_commit': save.git_commit,
                'has_changed': save.has_changed,
                'is_release': save.is_release,
                'release_id': save.release_id,
                'label_count': save.label_count
            })
        
        return history
    
    def get_version_snapshot(self, device_id: str, version: str) -> Optional[dict]:
        """获取版本快照"""
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return None
        
        return self.device_storage.get_version_snapshot(ata_code, device_id, version)
    
    def get_device_info(self, device_id: str) -> Optional[dict]:
        """获取设备信息（包含乐观锁所需的 base_commit）
        
        Returns:
            {
                'device_id': ...,
                'device_name': ...,
                'current_version': ...,
                'base_commit': ...,
                'updated_at': ...,
                'updated_by': ...,
                'labels': [...],
                ...
            }
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return None
        
        device_meta = self.device_storage.get_device_meta(ata_code, device_id)
        if not device_meta:
            return None
        
        labels = self.device_storage.get_labels(ata_code, device_id)
        base_commit = self.device_storage.get_device_base_commit(ata_code, device_id)
        
        return {
            'device_id': device_meta.device_id,
            'device_name': device_meta.device_name,
            'ata_code': device_meta.ata_code,
            'current_version': device_meta.current_version,
            'current_protocol_version_name': device_meta.current_protocol_version_name,
            'base_commit': base_commit or device_meta.current_commit,
            'updated_at': device_meta.updated_at,
            'updated_by': device_meta.updated_by,
            'description': device_meta.description,
            'status': device_meta.status,
            'labels': labels,
            'label_count': len(labels)
        }
    
    def restore_version(
        self,
        device_id: str,
        version: str,
        username: str,
        restore_summary: str = ''
    ) -> Tuple[bool, str, dict]:
        """恢复到指定历史版本
        
        将指定版本的 Labels 恢复为当前版本，会创建一个新的版本记录。
        
        Args:
            device_id: 设备 ID
            version: 要恢复的版本号
            username: 操作用户名
            restore_summary: 恢复说明
        
        Returns:
            (success, message, result_data)
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return False, f'无法从 device_id 提取 ATA 代码: {device_id}', {}
        
        # 获取版本快照
        snapshot = self.device_storage.get_version_snapshot(ata_code, device_id, version)
        if not snapshot:
            return False, f'版本 {version} 的快照不存在', {}
        
        # 获取快照中的 Labels
        snapshot_labels = snapshot.get('labels', [])
        if not snapshot_labels:
            return False, f'版本 {version} 的快照中没有 Labels', {}
        
        # 生成恢复说明
        if not restore_summary:
            restore_summary = f'从版本 {version} 恢复'
        
        # 使用保存方法保存恢复的 Labels
        return self.save_device_version(
            device_id=device_id,
            new_labels=snapshot_labels,
            username=username,
            change_summary=restore_summary,
            protocol_meta=snapshot.get('protocol_meta', {})
        )
    
    def get_version_labels(self, device_id: str, version: str) -> Optional[List[dict]]:
        """获取指定版本的 Labels（用于预览或恢复）
        
        Args:
            device_id: 设备 ID
            version: 版本号
        
        Returns:
            Labels 列表，如果版本不存在则返回 None
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return None
        
        snapshot = self.device_storage.get_version_snapshot(ata_code, device_id, version)
        if not snapshot:
            return None
        
        return snapshot.get('labels', [])
    
    def list_available_versions(self, device_id: str) -> List[dict]:
        """列出设备所有可恢复的版本
        
        Returns:
            版本列表，每个包含 version, created_at, created_by, label_count
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return []
        
        versions = self.device_storage.list_versions(ata_code, device_id)
        
        result = []
        for version in versions:
            snapshot = self.device_storage.get_version_snapshot(ata_code, device_id, version)
            if snapshot:
                result.append({
                    'version': version,
                    'created_at': snapshot.get('created_at', ''),
                    'created_by': snapshot.get('created_by', ''),
                    'label_count': snapshot.get('label_count', len(snapshot.get('labels', [])))
                })
        
        # 按版本号排序（降序，使用语义版本排序）
        def version_sort_key(item):
            """提取版本号的数字部分用于排序"""
            version = item.get('version', '')
            match = re.match(r'[Vv]?(\d+)\.?(\d*)', version)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2)) if match.group(2) else 0
                return (major, minor)
            return (0, 0)
        
        result.sort(key=version_sort_key, reverse=True)
        return result
    
    def delete_version(
        self,
        device_id: str,
        version: str,
        username: str
    ) -> Tuple[bool, str]:
        """删除指定的历史版本
        
        Args:
            device_id: 设备 ID
            version: 要删除的版本号
            username: 操作用户名
        
        Returns:
            (success, message)
        """
        ata_code = extract_ata_code(device_id)
        if not ata_code:
            return False, f'无法从 device_id 提取 ATA 代码: {device_id}'
        
        # 获取当前版本，不能删除当前版本
        device_meta = self.device_storage.get_device_meta(ata_code, device_id)
        if device_meta and device_meta.current_version == version:
            return False, '不能删除当前版本'
        
        # 使用写队列确保并发安全
        def do_delete():
            # 删除版本记录和快照（强一致性）
            success, message = self.device_storage.delete_release(ata_code, device_id, version)
            
            if not success:
                return False, message
            
            # Git 提交删除操作
            self.repo_manager.git_add(ata_code)
            self.repo_manager.git_commit(
                ata_code, 
                f'{device_id}: delete version {version} by {username}'
            )
            
            return True, message
        
        return self.repo_manager.execute_with_queue(ata_code, do_delete)


# 全局单例
_version_manager: Optional[VersionManager] = None


def get_version_manager() -> VersionManager:
    """获取全局 VersionManager 实例"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
