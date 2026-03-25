# -*- coding: utf-8 -*-
"""
协议导入主模块
整合文档抽取、LLM 解析、草稿管理的完整流程
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from document_extractors import (
    extract_document, preparse_arinc429_table, build_llm_prompt_context,
    build_llm_prompt_context_v2, convert_to_markdown,
    ExtractionResult
)
from llm_parser import (
    parse_protocol_with_llm, validate_parsed_result, enrich_labels_from_preparse
)
from database import get_db_connection


# 上传文件存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# 草稿状态常量
# ============================================================

class DraftStatus:
    UPLOADING = 'uploading'       # 上传中
    EXTRACTING = 'extracting'     # 抽取中
    PARSING = 'parsing'           # LLM 解析中
    DRAFT = 'draft'               # 草稿待审核
    CONFIRMED = 'confirmed'       # 已确认入库
    FAILED = 'failed'             # 失败
    CANCELLED = 'cancelled'       # 已取消


# ============================================================
# 数据库表初始化
# ============================================================

def init_import_tables():
    """初始化协议导入相关的数据库表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 导入草稿表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS protocol_import_drafts (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'uploading',
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                
                -- 文件信息
                original_filename TEXT,
                stored_filename TEXT,
                file_type TEXT,
                file_size INTEGER,
                
                -- 抽取结果
                extraction_result TEXT,
                preparse_result TEXT,
                
                -- LLM 解析结果
                llm_result TEXT,
                llm_errors TEXT,
                
                -- 最终草稿（用户可编辑）
                draft_protocol_meta TEXT,
                draft_device_info TEXT,
                draft_labels TEXT,
                
                -- 验证结果
                validation_errors TEXT,
                validation_warnings TEXT,
                
                -- 确认入库后的关联
                confirmed_device_id TEXT,
                confirmed_version_id INTEGER,
                
                -- 备注
                notes TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_drafts_status ON protocol_import_drafts(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_drafts_created_by ON protocol_import_drafts(created_by)')
        
        conn.commit()


# ============================================================
# 文件上传
# ============================================================

def handle_file_upload(file_storage, username: str) -> Tuple[str, Dict[str, Any]]:
    """处理文件上传
    
    Args:
        file_storage: Flask FileStorage 对象
        username: 上传用户名
    
    Returns:
        (draft_id, draft_info)
    """
    # 验证文件类型
    filename = file_storage.filename or ''
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ['.xlsx', '.xls', '.docx']:
        raise ValueError(f"不支持的文件类型: {ext}，仅支持 .xlsx, .xls, .docx")
    
    # 生成草稿 ID
    draft_id = str(uuid.uuid4())[:8]
    
    # 保存文件
    stored_filename = f"{draft_id}_{filename}"
    stored_path = os.path.join(UPLOAD_DIR, stored_filename)
    file_storage.save(stored_path)
    
    # 获取文件大小
    file_size = os.path.getsize(stored_path)
    
    # 创建草稿记录
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO protocol_import_drafts 
            (id, status, created_by, created_at, updated_at,
             original_filename, stored_filename, file_type, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            draft_id, DraftStatus.UPLOADING, username, now, now,
            filename, stored_filename, ext, file_size
        ))
        conn.commit()
    
    return draft_id, {
        'id': draft_id,
        'status': DraftStatus.UPLOADING,
        'filename': filename,
        'file_type': ext,
        'file_size': file_size
    }


# ============================================================
# 文档抽取与解析
# ============================================================

def process_draft(draft_id: str, use_llm: bool = True, protocol_type: str = '429') -> Dict[str, Any]:
    """处理草稿：抽取文档内容并解析
    
    Args:
        draft_id: 草稿 ID
        use_llm: 是否使用 LLM 解析
        protocol_type: 协议类型（'429', '422', 'CAN'）
    
    Returns:
        处理后的草稿信息
    """
    # 获取草稿信息
    draft = get_draft(draft_id)
    if not draft:
        raise ValueError(f"草稿不存在: {draft_id}")
    
    # 获取文件路径
    stored_filename = draft.get('stored_filename', '')
    file_path = os.path.join(UPLOAD_DIR, stored_filename)
    
    if not os.path.exists(file_path):
        _update_draft_status(draft_id, DraftStatus.FAILED, notes="文件不存在")
        raise ValueError(f"文件不存在: {file_path}")
    
    # 1. 抽取文档
    _update_draft_status(draft_id, DraftStatus.EXTRACTING)
    extraction_result = extract_document(file_path)
    
    if extraction_result.errors:
        _update_draft_status(
            draft_id, DraftStatus.FAILED,
            extraction_result=extraction_result.to_dict(),
            notes=f"抽取失败: {'; '.join(extraction_result.errors)}"
        )
        raise ValueError(f"文档抽取失败: {'; '.join(extraction_result.errors)}")
    
    # 2. 预解析表格
    preparse_results = []
    all_preparsed_labels = []
    
    for table in extraction_result.tables:
        preparse = preparse_arinc429_table(table)
        preparse_results.append(preparse)
        all_preparsed_labels.extend(preparse.get('parsed_labels', []))
    
    # 3. LLM 解析
    _update_draft_status(draft_id, DraftStatus.PARSING)
    
    llm_result = {}
    llm_errors = []
    
    if use_llm:
        # 使用 Markdown 格式构建上下文（更紧凑，适合 LLM）
        # gpt-4o-mini 支持 128K tokens，不需要严格限制
        context = build_llm_prompt_context_v2(extraction_result, preparse_results, max_chars=100000)
        llm_result, llm_errors = parse_protocol_with_llm(context, all_preparsed_labels, protocol_type)
    else:
        # 不使用 LLM，直接用预解析结果
        llm_result = {
            'protocol_meta': {
                'name': draft.get('original_filename', '未知协议'),
                'version': 'V1.0',
                'description': '由规则预解析生成'
            },
            'device_info': {
                'device_name': '待确认设备',
                'system_name': '待确认系统'
            },
            'labels': all_preparsed_labels,
            'parsing_notes': ['未使用 LLM，仅规则预解析']
        }
    
    # 4. 验证结果
    is_valid, validation_errors, validation_warnings = validate_parsed_result(llm_result)
    
    # 5. 合并结果
    if all_preparsed_labels and llm_result.get('labels'):
        llm_result['labels'] = enrich_labels_from_preparse(
            llm_result['labels'], all_preparsed_labels
        )
    
    # 6. 更新草稿
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE protocol_import_drafts SET
                status = ?,
                updated_at = ?,
                extraction_result = ?,
                preparse_result = ?,
                llm_result = ?,
                llm_errors = ?,
                draft_protocol_meta = ?,
                draft_device_info = ?,
                draft_labels = ?,
                validation_errors = ?,
                validation_warnings = ?
            WHERE id = ?
        ''', (
            DraftStatus.DRAFT,
            now,
            json.dumps(extraction_result.to_dict(), ensure_ascii=False),
            json.dumps(preparse_results, ensure_ascii=False),
            json.dumps(llm_result, ensure_ascii=False),
            json.dumps(llm_errors, ensure_ascii=False),
            json.dumps(llm_result.get('protocol_meta', {}), ensure_ascii=False),
            json.dumps(llm_result.get('device_info', {}), ensure_ascii=False),
            json.dumps(llm_result.get('labels', []), ensure_ascii=False),
            json.dumps(validation_errors, ensure_ascii=False),
            json.dumps(validation_warnings, ensure_ascii=False),
            draft_id
        ))
        conn.commit()
    
    return get_draft(draft_id)


def get_draft(draft_id: str) -> Optional[Dict[str, Any]]:
    """获取草稿信息
    
    Args:
        draft_id: 草稿 ID
    
    Returns:
        草稿信息字典
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM protocol_import_drafts WHERE id = ?', (draft_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        draft = dict(row)
        
        # 解析 JSON 字段
        json_fields = [
            'extraction_result', 'preparse_result', 'llm_result', 'llm_errors',
            'draft_protocol_meta', 'draft_device_info', 'draft_labels',
            'validation_errors', 'validation_warnings'
        ]
        
        for field in json_fields:
            if draft.get(field):
                try:
                    draft[field] = json.loads(draft[field])
                except json.JSONDecodeError:
                    pass
        
        return draft


def list_drafts(username: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出草稿
    
    Args:
        username: 可选，筛选指定用户的草稿
        status: 可选，筛选指定状态的草稿
    
    Returns:
        草稿列表
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = 'SELECT id, status, created_by, created_at, updated_at, original_filename, file_type, file_size FROM protocol_import_drafts'
        params = []
        conditions = []
        
        if username:
            conditions.append('created_by = ?')
            params.append(username)
        
        if status:
            conditions.append('status = ?')
            params.append(status)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def update_draft_labels(draft_id: str, labels: List[Dict]) -> Dict[str, Any]:
    """更新草稿的 Labels（用户编辑）
    
    Args:
        draft_id: 草稿 ID
        labels: 新的 Labels 列表
    
    Returns:
        更新后的草稿
    """
    draft = get_draft(draft_id)
    if not draft:
        raise ValueError(f"草稿不存在: {draft_id}")
    
    if draft.get('status') == DraftStatus.CONFIRMED:
        raise ValueError("草稿已确认入库，无法修改")
    
    # 重新验证
    result = {'labels': labels}
    is_valid, validation_errors, validation_warnings = validate_parsed_result(result)
    
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE protocol_import_drafts SET
                updated_at = ?,
                draft_labels = ?,
                validation_errors = ?,
                validation_warnings = ?
            WHERE id = ?
        ''', (
            now,
            json.dumps(labels, ensure_ascii=False),
            json.dumps(validation_errors, ensure_ascii=False),
            json.dumps(validation_warnings, ensure_ascii=False),
            draft_id
        ))
        conn.commit()
    
    return get_draft(draft_id)


def update_draft_meta(draft_id: str, protocol_meta: Dict = None, device_info: Dict = None) -> Dict[str, Any]:
    """更新草稿的元信息
    
    Args:
        draft_id: 草稿 ID
        protocol_meta: 协议元信息
        device_info: 设备信息
    
    Returns:
        更新后的草稿
    """
    draft = get_draft(draft_id)
    if not draft:
        raise ValueError(f"草稿不存在: {draft_id}")
    
    if draft.get('status') == DraftStatus.CONFIRMED:
        raise ValueError("草稿已确认入库，无法修改")
    
    now = datetime.now().isoformat()
    updates = ['updated_at = ?']
    params = [now]
    
    if protocol_meta is not None:
        updates.append('draft_protocol_meta = ?')
        params.append(json.dumps(protocol_meta, ensure_ascii=False))
    
    if device_info is not None:
        updates.append('draft_device_info = ?')
        params.append(json.dumps(device_info, ensure_ascii=False))
    
    params.append(draft_id)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE protocol_import_drafts SET {', '.join(updates)} WHERE id = ?
        ''', params)
        conn.commit()
    
    return get_draft(draft_id)


# ============================================================
# 确认入库
# ============================================================

def confirm_draft(
    draft_id: str,
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    system_id: Optional[str] = None,
    system_name: Optional[str] = None,
    version_name: Optional[str] = None,
    username: Optional[str] = None
) -> Dict[str, Any]:
    """确认草稿并入库
    
    Args:
        draft_id: 草稿 ID
        device_id: 设备 ID（可选，不提供则自动生成）
        device_name: 设备名称
        system_id: 系统 ID（父节点）
        system_name: 系统名称
        version_name: 版本名称
        username: 操作用户
    
    Returns:
        入库结果
    """
    from database import db_create_device, db_save_labels, db_get_device
    from device_manager import generate_device_id
    
    draft = get_draft(draft_id)
    if not draft:
        raise ValueError(f"草稿不存在: {draft_id}")
    
    if draft.get('status') == DraftStatus.CONFIRMED:
        raise ValueError("草稿已确认入库")
    
    # 获取草稿数据
    protocol_meta = draft.get('draft_protocol_meta', {})
    device_info = draft.get('draft_device_info', {})
    labels = draft.get('draft_labels', [])
    
    if not labels:
        raise ValueError("草稿中没有 Labels")
    
    # 清理 Labels 中的内部字段
    clean_labels = []
    for label in labels:
        clean_label = {k: v for k, v in label.items() if not k.startswith('_')}
        clean_labels.append(clean_label)
    
    # 确定设备名称
    final_device_name = device_name or device_info.get('device_name', '导入设备')
    final_system_name = system_name or device_info.get('system_name', '导入系统')
    final_version = version_name or protocol_meta.get('version', 'V1.0')
    
    # 生成设备 ID
    if not device_id:
        device_id = generate_device_id([final_system_name, final_device_name])
    
    # 检查系统节点是否存在
    system_pk = None
    if system_id:
        system_device = db_get_device(system_id)
        if system_device:
            system_pk = system_device['id']
    
    # 如果系统不存在，创建系统节点
    if not system_pk and final_system_name:
        system_device_id = generate_device_id([final_system_name])
        existing_system = db_get_device(system_device_id)
        if existing_system:
            system_pk = existing_system['id']
        else:
            system_pk = db_create_device(
                device_id=system_device_id,
                name=final_system_name,
                parent_id=None,
                is_device=False
            )
    
    # 检查设备是否已存在
    existing_device = db_get_device(device_id)
    if existing_device:
        device_pk = existing_device['id']
    else:
        # 创建设备
        device_pk = db_create_device(
            device_id=device_id,
            name=final_device_name,
            parent_id=system_pk,
            is_device=True,
            device_version=final_version,
            current_version_name=final_version,
            description=protocol_meta.get('description', '')
        )
    
    if not device_pk:
        raise ValueError("创建设备失败")
    
    # 创建协议版本
    version_id = None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO device_protocol_versions (device_id, version_name, version)
                VALUES (?, ?, ?)
            ''', (device_pk, final_version, final_version))
            conn.commit()
            version_id = cursor.lastrowid
        except Exception:
            # 版本可能已存在
            cursor.execute('''
                SELECT id FROM device_protocol_versions 
                WHERE device_id = ? AND version_name = ?
            ''', (device_pk, final_version))
            row = cursor.fetchone()
            if row:
                version_id = row[0]
    
    # 保存 Labels
    db_save_labels(device_id, clean_labels, version_id)
    
    # 更新草稿状态
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE protocol_import_drafts SET
                status = ?,
                updated_at = ?,
                confirmed_device_id = ?,
                confirmed_version_id = ?,
                notes = ?
            WHERE id = ?
        ''', (
            DraftStatus.CONFIRMED,
            now,
            device_id,
            version_id,
            f"已入库到设备 {final_device_name} 版本 {final_version}",
            draft_id
        ))
        conn.commit()
    
    return {
        'success': True,
        'device_id': device_id,
        'device_name': final_device_name,
        'version_id': version_id,
        'version_name': final_version,
        'label_count': len(clean_labels)
    }


def delete_draft(draft_id: str) -> bool:
    """删除草稿
    
    Args:
        draft_id: 草稿 ID
    
    Returns:
        是否删除成功
    """
    draft = get_draft(draft_id)
    if not draft:
        return False
    
    # 删除关联的上传文件
    stored_filename = draft.get('stored_filename', '')
    if stored_filename:
        file_path = os.path.join(UPLOAD_DIR, stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # 删除数据库记录
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM protocol_import_drafts WHERE id = ?', (draft_id,))
        conn.commit()
        return cursor.rowcount > 0


def _update_draft_status(draft_id: str, status: str, **kwargs):
    """更新草稿状态
    
    Args:
        draft_id: 草稿 ID
        status: 新状态
        **kwargs: 其他要更新的字段
    """
    now = datetime.now().isoformat()
    updates = ['status = ?', 'updated_at = ?']
    params = [status, now]
    
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        updates.append(f'{key} = ?')
        params.append(value)
    
    params.append(draft_id)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE protocol_import_drafts SET {', '.join(updates)} WHERE id = ?
        ''', params)
        conn.commit()


# 初始化时创建表
init_import_tables()
