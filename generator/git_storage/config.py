# -*- coding: utf-8 -*-
"""
Git 存储配置
定义 ATA repo 目录结构、元数据文件格式和版本发布文件格式
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


# ============================================================
# 目录结构常量
# ============================================================

# ATA repo 根目录（相对于项目根目录）
GIT_REPOS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'git_repos')

# repo 内目录结构
REPO_META_FILE = 'repo_meta.json'
DEVICES_DIR = 'devices'
DEVICE_META_FILE = 'device_meta.json'
CURRENT_DIR = 'current'
PROTOCOL_FILE = 'protocol.json'
LABELS_DIR = 'labels'
VERSIONS_DIR = 'versions'
HISTORY_DIR = 'history'
RELEASES_FILE = 'releases.json'  # 发布历史（正式版本节点）
SAVES_FILE = 'saves.json'        # 保存记录（完整保存时间线）
DOCS_DIR = 'docs'


@dataclass
class GitStorageConfig:
    """Git 存储配置"""
    
    # 仓库根目录
    repos_root: str = GIT_REPOS_ROOT
    
    # 锁配置
    lock_timeout_seconds: int = 90  # 锁超时时间
    heartbeat_interval_seconds: int = 25  # 心跳间隔
    
    # ATA 写队列配置
    write_queue_timeout_seconds: int = 30  # 写队列等待超时
    
    # Git 配置
    git_author_name: str = 'Protocol Platform'
    git_author_email: str = 'protocol@system.local'
    
    def get_ata_repo_path(self, ata_code: str) -> str:
        """获取 ATA repo 路径"""
        repo_name = f'protocol-{ata_code.lower()}'
        return os.path.join(self.repos_root, repo_name)
    
    def get_device_path(self, ata_code: str, device_id: str) -> str:
        """获取设备目录路径"""
        repo_path = self.get_ata_repo_path(ata_code)
        return os.path.join(repo_path, DEVICES_DIR, device_id)
    
    def get_device_current_path(self, ata_code: str, device_id: str) -> str:
        """获取设备当前版本目录路径"""
        device_path = self.get_device_path(ata_code, device_id)
        return os.path.join(device_path, CURRENT_DIR)
    
    def get_device_labels_path(self, ata_code: str, device_id: str) -> str:
        """获取设备 Labels 目录路径"""
        current_path = self.get_device_current_path(ata_code, device_id)
        return os.path.join(current_path, LABELS_DIR)
    
    def get_device_versions_path(self, ata_code: str, device_id: str) -> str:
        """获取设备版本快照目录路径"""
        device_path = self.get_device_path(ata_code, device_id)
        return os.path.join(device_path, VERSIONS_DIR)
    
    def get_device_history_path(self, ata_code: str, device_id: str) -> str:
        """获取设备历史目录路径"""
        device_path = self.get_device_path(ata_code, device_id)
        return os.path.join(device_path, HISTORY_DIR)


# ============================================================
# 元数据文件格式定义
# ============================================================

@dataclass
class RepoMeta:
    """ATA repo 元数据"""
    repo_type: str = 'ata_protocol_repo'
    ata_code: str = ''
    ata_name: str = ''
    schema_version: str = '1.0'
    created_at: str = ''
    
    def to_dict(self) -> dict:
        return {
            'repo_type': self.repo_type,
            'ata_code': self.ata_code,
            'ata_name': self.ata_name,
            'schema_version': self.schema_version,
            'created_at': self.created_at or datetime.now().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RepoMeta':
        return cls(
            repo_type=data.get('repo_type', 'ata_protocol_repo'),
            ata_code=data.get('ata_code', ''),
            ata_name=data.get('ata_name', ''),
            schema_version=data.get('schema_version', '1.0'),
            created_at=data.get('created_at', '')
        )


@dataclass
class DeviceMeta:
    """设备元数据 - 未来迁移到按设备 repo 最关键的文件"""
    device_id: str = ''
    device_name: str = ''
    ata_code: str = ''
    parent_path: List[str] = field(default_factory=list)
    current_version: str = 'V1.0'
    current_protocol_version_name: str = ''
    current_commit: str = ''
    updated_at: str = ''
    updated_by: str = ''
    description: str = ''
    status: str = 'active'  # active, archived, deprecated
    
    def to_dict(self) -> dict:
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'ata_code': self.ata_code,
            'parent_path': self.parent_path,
            'current_version': self.current_version,
            'current_protocol_version_name': self.current_protocol_version_name,
            'current_commit': self.current_commit,
            'updated_at': self.updated_at or datetime.now().isoformat(),
            'updated_by': self.updated_by,
            'description': self.description,
            'status': self.status
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceMeta':
        return cls(
            device_id=data.get('device_id', ''),
            device_name=data.get('device_name', ''),
            ata_code=data.get('ata_code', ''),
            parent_path=data.get('parent_path', []),
            current_version=data.get('current_version', 'V1.0'),
            current_protocol_version_name=data.get('current_protocol_version_name', ''),
            current_commit=data.get('current_commit', ''),
            updated_at=data.get('updated_at', ''),
            updated_by=data.get('updated_by', ''),
            description=data.get('description', ''),
            status=data.get('status', 'active')
        )


@dataclass
class ProtocolMeta:
    """协议元信息"""
    name: str = ''
    version: str = ''
    description: str = ''
    author: str = ''
    created_at: str = ''
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'created_at': self.created_at or datetime.now().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProtocolMeta':
        return cls(
            name=data.get('name', ''),
            version=data.get('version', ''),
            description=data.get('description', ''),
            author=data.get('author', ''),
            created_at=data.get('created_at', '')
        )


@dataclass
class VersionInfo:
    """版本信息"""
    version: str = ''
    created_at: str = ''
    created_by: str = ''
    
    def to_dict(self) -> dict:
        return {
            'version': self.version,
            'created_at': self.created_at or datetime.now().isoformat(),
            'created_by': self.created_by
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VersionInfo':
        return cls(
            version=data.get('version', ''),
            created_at=data.get('created_at', ''),
            created_by=data.get('created_by', '')
        )


@dataclass
class ChangeStats:
    """变更统计"""
    added: int = 0
    modified: int = 0
    deleted: int = 0
    
    def to_dict(self) -> dict:
        return {
            'added': self.added,
            'modified': self.modified,
            'deleted': self.deleted
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ChangeStats':
        return cls(
            added=data.get('added', 0),
            modified=data.get('modified', 0),
            deleted=data.get('deleted', 0)
        )


@dataclass
class ReleaseRecord:
    """版本发布记录 - 产品层历史，不依赖 Git 原始日志
    
    包含：
    - 基础信息：release_id, device_id, from_version, to_version
    - 变更摘要：summary, change_stats
    - Git 关联：git_commit, git_tag
    - 详细 diff：diff_details（新增，包含 added_details, removed_details, modified_details）
    - 元信息：created_by, created_at, label_count
    """
    release_id: str = ''
    device_id: str = ''
    from_version: str = ''
    to_version: str = ''
    summary: str = ''
    change_stats: ChangeStats = field(default_factory=ChangeStats)
    git_commit: str = ''
    git_tag: str = ''
    created_by: str = ''
    created_at: str = ''
    # 新增：详细 diff 信息
    diff_details: Dict = field(default_factory=dict)
    # 新增：该版本的 label 数量
    label_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            'release_id': self.release_id,
            'device_id': self.device_id,
            'from_version': self.from_version,
            'to_version': self.to_version,
            'summary': self.summary,
            'change_stats': self.change_stats.to_dict() if isinstance(self.change_stats, ChangeStats) else self.change_stats,
            'git_commit': self.git_commit,
            'git_tag': self.git_tag,
            'created_by': self.created_by,
            'created_at': self.created_at or datetime.now().isoformat(),
            'diff_details': self.diff_details,
            'label_count': self.label_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ReleaseRecord':
        change_stats_data = data.get('change_stats', {})
        if isinstance(change_stats_data, dict):
            change_stats = ChangeStats.from_dict(change_stats_data)
        else:
            change_stats = ChangeStats()
        
        return cls(
            release_id=data.get('release_id', ''),
            device_id=data.get('device_id', ''),
            from_version=data.get('from_version', ''),
            to_version=data.get('to_version', ''),
            summary=data.get('summary', ''),
            change_stats=change_stats,
            git_commit=data.get('git_commit', ''),
            git_tag=data.get('git_tag', ''),
            created_by=data.get('created_by', ''),
            created_at=data.get('created_at', ''),
            diff_details=data.get('diff_details', {}),
            label_count=data.get('label_count', 0)
        )


@dataclass
class SaveRecord:
    """保存记录 - 完整保存时间线，每次保存一条
    
    与 ReleaseRecord 的区别：
    - SaveRecord：记录每一次保存操作，无论是否产生新版本
    - ReleaseRecord：只记录产生新版本的保存（正式发布节点）
    
    这样用户可以：
    - 查看完整的保存历史（包括无变更的保存）
    - 查看正式版本历史（只看版本节点）
    """
    save_id: str = ''           # 保存记录 ID
    device_id: str = ''         # 设备 ID
    version: str = ''           # 保存时的版本号
    summary: str = ''           # 变更说明
    change_stats: ChangeStats = field(default_factory=ChangeStats)
    diff_details: Dict = field(default_factory=dict)  # 详细 diff
    git_commit: str = ''        # Git commit hash
    has_changed: bool = False   # 是否有实际变更
    is_release: bool = False    # 是否是正式发布（产生新版本）
    release_id: str = ''        # 关联的 release_id（如果是发布）
    created_by: str = ''        # 操作者
    created_at: str = ''        # 保存时间
    label_count: int = 0        # 保存时的 label 数量
    
    def to_dict(self) -> dict:
        return {
            'save_id': self.save_id,
            'device_id': self.device_id,
            'version': self.version,
            'summary': self.summary,
            'change_stats': self.change_stats.to_dict() if isinstance(self.change_stats, ChangeStats) else self.change_stats,
            'diff_details': self.diff_details,
            'git_commit': self.git_commit,
            'has_changed': self.has_changed,
            'is_release': self.is_release,
            'release_id': self.release_id,
            'created_by': self.created_by,
            'created_at': self.created_at or datetime.now().isoformat(),
            'label_count': self.label_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SaveRecord':
        change_stats_data = data.get('change_stats', {})
        if isinstance(change_stats_data, dict):
            change_stats = ChangeStats.from_dict(change_stats_data)
        else:
            change_stats = ChangeStats()
        
        return cls(
            save_id=data.get('save_id', ''),
            device_id=data.get('device_id', ''),
            version=data.get('version', ''),
            summary=data.get('summary', ''),
            change_stats=change_stats,
            diff_details=data.get('diff_details', {}),
            git_commit=data.get('git_commit', ''),
            has_changed=data.get('has_changed', False),
            is_release=data.get('is_release', False),
            release_id=data.get('release_id', ''),
            created_by=data.get('created_by', ''),
            created_at=data.get('created_at', ''),
            label_count=data.get('label_count', 0)
        )


def generate_save_id(device_id: str, timestamp: str = None) -> str:
    """生成保存记录 ID"""
    if not timestamp:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f'{device_id}_save_{timestamp}'


@dataclass
class LabelDefinition:
    """Label 定义"""
    label_oct: str = ''
    name: str = ''
    direction: str = ''
    sources: List[str] = field(default_factory=list)
    data_type: str = ''
    unit: str = ''
    range_desc: str = ''
    resolution: Optional[float] = None
    reserved_bits: str = ''
    notes: str = ''
    discrete_bits: Dict = field(default_factory=dict)
    special_fields: List = field(default_factory=list)
    bnr_fields: List = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            'label_oct': self.label_oct,
            'name': self.name,
            'direction': self.direction,
            'sources': self.sources,
            'data_type': self.data_type,
            'unit': self.unit,
            'range': self.range_desc,
            'resolution': self.resolution,
            'reserved_bits': self.reserved_bits,
            'notes': self.notes,
            'discrete_bits': self.discrete_bits,
            'special_fields': self.special_fields,
            'bnr_fields': self.bnr_fields
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LabelDefinition':
        return cls(
            label_oct=data.get('label_oct', ''),
            name=data.get('name', ''),
            direction=data.get('direction', ''),
            sources=data.get('sources', []),
            data_type=data.get('data_type', ''),
            unit=data.get('unit', ''),
            range_desc=data.get('range', ''),
            resolution=data.get('resolution'),
            reserved_bits=data.get('reserved_bits', ''),
            notes=data.get('notes', ''),
            discrete_bits=data.get('discrete_bits', {}),
            special_fields=data.get('special_fields', []),
            bnr_fields=data.get('bnr_fields', [])
        )


# ============================================================
# ATA 系统映射
# ============================================================

ATA_SYSTEMS = {
    'ata21': {'code': 'ATA21', 'name': '空调系统'},
    'ata23': {'code': 'ATA23', 'name': '通信系统'},
    'ata24': {'code': 'ATA24', 'name': '电源系统'},
    'ata27': {'code': 'ATA27', 'name': '飞行控制系统'},
    'ata32': {'code': 'ATA32', 'name': '起落架系统'},
    'ata34': {'code': 'ATA34', 'name': '导航系统'},
    'ata35': {'code': 'ATA35', 'name': '氧气系统'},
    'ata36': {'code': 'ATA36', 'name': '气动系统'},
    'ata38': {'code': 'ATA38', 'name': '水/废水系统'},
    'ata45': {'code': 'ATA45', 'name': '中央维护系统'},
    'ata46': {'code': 'ATA46', 'name': '信息系统'},
    'ata49': {'code': 'ATA49', 'name': '机载辅助动力'},
}


def extract_ata_code(device_id: str, device_info: dict = None) -> Optional[str]:
    """从 device_id 或设备信息提取 ATA 代码
    
    Args:
        device_id: 设备 ID，如 'ata32_32_3' 或 'sys_1774252828_100_15'
        device_info: 可选的设备信息字典，包含 name, parent_path 等
    
    Returns:
        ATA 代码，如 'ata32'，如果无法提取则返回 'default'
    
    提取策略：
    1. 从 device_id 直接提取（如 ata32_xxx -> ata32）
    2. 从 device_info 的 parent_path 或 name 中提取
    3. 从数据库查询设备的父路径
    4. 返回 'default' 作为默认 ATA
    """
    import re
    
    # 策略1: 从 device_id 直接提取
    match = re.match(r'(ata\d+)', device_id.lower())
    if match:
        return match.group(1)
    
    # 策略2: 从 device_info 提取
    if device_info:
        # 从 parent_path 提取
        parent_path = device_info.get('parent_path', [])
        if isinstance(parent_path, list):
            for part in parent_path:
                ata_match = re.search(r'ATA\s*(\d+)', str(part), re.IGNORECASE)
                if ata_match:
                    return f'ata{ata_match.group(1)}'
        
        # 从 name 提取
        name = device_info.get('name', '')
        ata_match = re.search(r'ATA\s*(\d+)', name, re.IGNORECASE)
        if ata_match:
            return f'ata{ata_match.group(1)}'
    
    # 策略3: 从数据库查询
    try:
        from database import db_get_device, db_get_device_by_pk
        device = db_get_device(device_id)
        if device:
            # 从设备名称提取
            name = device.get('name', '')
            ata_match = re.search(r'ATA\s*(\d+)', name, re.IGNORECASE)
            if ata_match:
                return f'ata{ata_match.group(1)}'
            
            # 从父节点路径提取（需要遍历设备树）
            # 注意：parent_id 是主键，需要用 db_get_device_by_pk 查询
            parent_id = device.get('parent_id')
            while parent_id:
                parent = db_get_device_by_pk(parent_id)
                if parent:
                    parent_name = parent.get('name', '')
                    ata_match = re.search(r'ATA\s*(\d+)', parent_name, re.IGNORECASE)
                    if ata_match:
                        return f'ata{ata_match.group(1)}'
                    parent_id = parent.get('parent_id')
                else:
                    break
    except Exception:
        pass
    
    # 策略4: 返回默认值
    return 'default'


def get_ata_info(ata_code: str) -> Optional[dict]:
    """获取 ATA 系统信息
    
    Args:
        ata_code: ATA 代码，如 'ata32' 或 'ATA32'
    
    Returns:
        ATA 系统信息字典，如果不存在则返回 None
    """
    return ATA_SYSTEMS.get(ata_code.lower())


def generate_release_id(device_id: str, version: str) -> str:
    """生成发布记录 ID
    
    Args:
        device_id: 设备 ID
        version: 版本号，如 'V6.0'
    
    Returns:
        发布记录 ID，如 'ata32_32_3_v6_0'
    """
    version_part = version.lower().replace('.', '_')
    return f'{device_id}_{version_part}'


def generate_git_tag(device_id: str, version: str) -> str:
    """生成 Git tag 名称
    
    Args:
        device_id: 设备 ID
        version: 版本号，如 'V6.0'
    
    Returns:
        Git tag 名称，如 'ata32_32_3-v6.0'
    """
    version_part = version.lower()
    return f'{device_id}-{version_part}'
