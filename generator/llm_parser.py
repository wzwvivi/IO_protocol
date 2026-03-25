# -*- coding: utf-8 -*-
"""
LLM 协议解析模块
调用 LLM API 将文档内容解析为标准化的 ARINC429 协议配置
"""

import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


# LLM 配置（从环境变量读取）
def get_llm_config():
    """动态获取 LLM 配置"""
    return {
        'api_base_url': os.environ.get('LLM_API_BASE_URL', 'https://api.openai.com/v1'),
        'api_key': os.environ.get('LLM_API_KEY', ''),
        'model': os.environ.get('LLM_MODEL', 'gpt-4o'),
        'timeout': int(os.environ.get('LLM_TIMEOUT', '120'))
    }

# 兼容旧代码的全局变量（但实际使用时会动态获取）
LLM_API_BASE_URL = os.environ.get('LLM_API_BASE_URL', 'https://api.openai.com/v1')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_MODEL = os.environ.get('LLM_MODEL', 'gpt-4o')
LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '120'))


# 标准 Label 结构的 JSON Schema
LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "label_oct": {"type": "string", "description": "八进制 Label 值，如 '115', '270'"},
        "name": {"type": "string", "description": "信号名称"},
        "direction": {"type": "string", "description": "数据方向，如 'TX', 'RX', 'RDIU -> SCU'"},
        "sources": {"type": "array", "items": {"type": "string"}, "description": "数据来源列表"},
        "discrete_bits": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "离散位定义，key 为位号，value 为描述"
        },
        "special_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "bits": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    "type": {"type": "string", "enum": ["enum", "uint"]},
                    "values": {"type": "object", "additionalProperties": {"type": "string"}}
                }
            },
            "description": "多位枚举字段"
        },
        "bnr_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "data_bits": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    "sign_bit": {"type": ["integer", "null"]},
                    "resolution": {"type": "number"},
                    "unit": {"type": "string"}
                }
            },
            "description": "BNR 数值字段"
        },
        "notes": {"type": "string", "description": "备注信息"}
    },
    "required": ["label_oct", "name"]
}


# 系统提示词（基础版）
SYSTEM_PROMPT_BASE = """你是一个专业的航空电子协议解析专家。你的任务是从用户提供的协议文档内容中提取结构化的协议定义。

⚠️ **重要：方向(direction)和源设备(sources)必须从文档中提取，不要假设任何固定值！**

你需要输出的 JSON 格式：
{
  "protocol_meta": {
    "name": "协议名称",
    "version": "版本号",
    "description": "协议描述"
  },
  "device_info": {
    "device_name": "设备名称",
    "system_name": "所属系统"
  },
  "labels": [
    {
      "label_oct": "115",
      "name": "信号名称",
      "direction": "从文档提取的源 -> 从文档提取的目的",
      "sources": ["从文档提取的源设备名称"],
      "discrete_bits": {},
      "special_fields": [],
      "bnr_fields": [
        {
          "name": "数据名",
          "data_bits": [17, 28],
          "sign_bit": 29,
          "resolution": 0.014653,
          "unit": "°"
        }
      ],
      "notes": "备注"
    }
  ],
  "parsing_notes": ["解析过程中的说明或不确定项"]
}
"""

# ARINC429 专用系统提示词（精简版）
SYSTEM_PROMPT_ARINC429 = """你是 ARINC429 协议解析专家。

## 位定义类型判断（关键！）

### 1. 单 bit 离散 → `discrete_bits`
- **必须是单个位**，且说明包含 `0=xxx, 1=yyy`
- 格式：`{"位号": "字段名: 0=含义, 1=含义"}`
- 例：Bit 12 说明 "0=Present, 1=Not present" → `{"12": "...: 0=Present, 1=Not present"}`

### 2. BNR 数值 → `bnr_fields`（重要！）
- **多个连续位有相同或相似的说明** → 合并为一个 BNR 字段
- 例：Bit 16,17,18,19 都是 "Number of Satellites Visible" → `{"name": "Number of Satellites Visible", "data_bits": [16, 19]}`
- 例：Bit 20,21,22,23 都是 "Number of Satellites Tracked" → `{"name": "Number of Satellites Tracked", "data_bits": [20, 23]}`
- **不要把多位数值拆成多个 discrete_bits！**

### 3. 多 bit 枚举 → `special_fields`
- 多个连续位，且**明确列出每个组合值的含义**（如 00=xxx, 01=yyy, 10=zzz）
- 格式：`{"name": "字段名", "bits": [起始, 结束], "type": "enum", "values": {"0": "含义A", "1": "含义B"}}`

### 4. 忽略
Label编码(1-8), SDI(9-10), SSM(30-31), 校验位(32), Pad/保留

## 解析规则

- **合并相同说明的连续位**：bit 16-19 都是 "Satellites Visible" → 一个 bnr_fields
- 方向从"源"/"目的"提取，格式：`源 -> 目的`
- 每个 label_oct 只输出一次
- 没有分辨率的数据，resolution 填 null

## 输出格式

```json
{
  "protocol_meta": {"name": "协议名", "version": "版本", "description": "描述"},
  "device_info": {"device_name": "设备名", "system_name": "系统名"},
  "labels": [
    {
      "label_oct": "132",
      "name": "True Heading",
      "direction": "IRS -> CPE",
      "sources": ["IRS"],
      "discrete_bits": {},
      "special_fields": [],
      "bnr_fields": [
        {"name": "True Heading", "data_bits": [11, 28], "sign_bit": 29, "resolution": 0.0055, "unit": "degrees"}
      ],
      "notes": "范围-180~180"
    },
    {
      "label_oct": "273",
      "name": "GPS Sensor Status",
      "direction": "GPS -> CPE",
      "sources": ["GPS"],
      "discrete_bits": {
        "12": "DADC/FMS source present: 0=Present, 1=Not present",
        "13": "DADC/FMS source: 0=Primary, 1=Secondary",
        "14": "IRS/FMS source present: 0=Present, 1=Not present",
        "15": "IRS/FMS source: 0=Primary, 1=Secondary",
        "29": "MSB Satellites Tracked: 1=>15, 0=≤15"
      },
      "special_fields": [
        {"name": "GPS Sensor Operational Mode", "bits": [24, 28], "type": "enum", "values": {"0": "Init", "1": "Nav", "2": "Fault"}}
      ],
      "bnr_fields": [
        {"name": "Number of Satellites Visible", "data_bits": [16, 19], "sign_bit": null, "resolution": null, "unit": ""},
        {"name": "Number of Satellites Tracked", "data_bits": [20, 23], "sign_bit": null, "resolution": null, "unit": ""}
      ],
      "notes": ""
    }
  ],
  "parsing_notes": []
}
```

## 注意事项

- sign_bit 无符号时填 `null`
- resolution 是数字或 `null`
- 同一个 Label 只输出一次
- 方向必须从文档提取

## ⚠️ 重要：必须提取所有 Labels！

- **不要遗漏任何 Label**
- 如果预解析结果中有 N 个 Label，你的输出也应该有 N 个 Label
- 即使某些 Label 的字段定义不完整，也要输出（可以留空字段）
- 宁可输出不完整的 Label，也不要遗漏
"""

# RS422 专用系统提示词
SYSTEM_PROMPT_RS422 = """你是一个 RS422 串行通信协议专家。

## RS422 协议规范

### 基本特征
- **传输方式**: 全双工/半双工串行通信
- **信号类型**: 差分信号
- **传输距离**: 最大 1200m
- **传输速率**: 最高 10 Mbps

### 数据帧格式
通常包含：
- 帧头/同步字
- 设备地址
- 命令字
- 数据区
- 校验（CRC/Checksum）
- 帧尾

请提取帧结构定义、各字段的位置、长度、含义、校验算法等信息。
""" + SYSTEM_PROMPT_BASE

# CAN 专用系统提示词
SYSTEM_PROMPT_CAN = """你是一个 CAN 总线协议专家。

## CAN 协议规范

### 基本特征
- **标准帧 ID**: 11 位
- **扩展帧 ID**: 29 位
- **数据长度**: 0-8 字节
- **传输速率**: 最高 1 Mbps

### 数据帧格式
| 字段 | 说明 |
|------|------|
| CAN ID | 消息标识符 |
| DLC | 数据长度码 |
| Data | 数据域（0-8字节）|

请提取 CAN ID 列表、每个 ID 对应的数据定义、信号的起始位、长度、因子、偏移量、单位和范围。
""" + SYSTEM_PROMPT_BASE

# 默认使用 ARINC429
SYSTEM_PROMPT = SYSTEM_PROMPT_ARINC429


def get_system_prompt(protocol_type: str = '429') -> str:
    """根据协议类型获取对应的系统提示词"""
    prompts = {
        '429': SYSTEM_PROMPT_ARINC429,
        'ARINC429': SYSTEM_PROMPT_ARINC429,
        '422': SYSTEM_PROMPT_RS422,
        'RS422': SYSTEM_PROMPT_RS422,
        'CAN': SYSTEM_PROMPT_CAN,
    }
    return prompts.get(protocol_type.upper(), SYSTEM_PROMPT_ARINC429)


def parse_protocol_with_llm(
    context: str,
    preparsed_labels: Optional[List[Dict]] = None,
    protocol_type: str = '429'
) -> Tuple[Dict[str, Any], List[str]]:
    """使用 LLM 解析协议内容
    
    Args:
        context: 文档上下文（由 document_extractors 生成）
        preparsed_labels: 预解析的 Labels（可选，提供给 LLM 参考）
        protocol_type: 协议类型（'429', '422', 'CAN'）
    
    Returns:
        (解析结果, 错误列表)
    """
    errors = []
    
    # 动态获取配置
    config = get_llm_config()
    api_key = config['api_key']
    
    if not api_key:
        errors.append("未配置 LLM_API_KEY 环境变量")
        return _fallback_parse(preparsed_labels), errors
    
    # 根据协议类型选择提示词
    protocol_name_map = {
        '429': 'ARINC429',
        'ARINC429': 'ARINC429',
        '422': 'RS422',
        'RS422': 'RS422',
        'CAN': 'CAN'
    }
    protocol_display_name = protocol_name_map.get(protocol_type.upper(), 'ARINC429')
    
    # 构建用户消息
    user_message_parts = [
        f"请从以下协议文档内容中提取 {protocol_display_name} 协议定义：",
        "",
        context,
    ]
    
    if preparsed_labels:
        preparsed_count = len(preparsed_labels)
        user_message_parts.extend([
            "",
            f"## 预解析结果（共 {preparsed_count} 个 Labels，供参考）",
            "",
            f"⚠️ **重要：请确保输出包含所有 {preparsed_count} 个 Labels！不要遗漏任何一个！**",
            "",
            json.dumps(preparsed_labels, ensure_ascii=False, indent=2)
        ])
    
    user_message = '\n'.join(user_message_parts)
    
    try:
        system_prompt = get_system_prompt(protocol_type)
        result = _call_llm_api(user_message, system_prompt)
        return result, errors
    except Exception as e:
        errors.append(f"LLM 调用失败: {str(e)}")
        return _fallback_parse(preparsed_labels), errors


def _call_llm_api(user_message: str, system_prompt: str = None) -> Dict[str, Any]:
    """调用 LLM API
    
    Args:
        user_message: 用户消息
        system_prompt: 系统提示词（可选，默认使用 ARINC429）
    
    Returns:
        解析后的 JSON 结果
    """
    import urllib.request
    import urllib.error
    import ssl
    
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT_ARINC429
    
    # 动态获取配置
    config = get_llm_config()
    api_base_url = config['api_base_url']
    api_key = config['api_key']
    model = config['model']
    timeout = config['timeout']
    
    # 构建请求
    url = f"{api_base_url}/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message}
        ],
        'temperature': 0.1
    }
    
    # 根据模型选择正确的 token 参数（限制输出长度，防止截断）
    # gpt-5.x 系列使用 max_completion_tokens，其他模型使用 max_tokens
    # 如果不需要限制，可以注释掉这部分
    if model.startswith('gpt-5'):
        payload['max_completion_tokens'] = 32000  # gpt-5 支持更大的输出
    else:
        payload['max_tokens'] = 16000
    
    # Groq 不支持 response_format，只有 OpenAI 支持
    if 'openai.com' in api_base_url:
        payload['response_format'] = {'type': 'json_object'}
    
    data = json.dumps(payload).encode('utf-8')
    
    # 允许自签名证书（开发环境）
    ctx = ssl.create_default_context()
    if os.environ.get('LLM_ALLOW_INSECURE', '').lower() == 'true':
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    
    # 重试机制
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # 发送请求
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
            break  # 成功，退出重试循环
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            last_error = f"HTTP {e.code}: {error_body}"
            # 429 错误（速率限制）不重试
            if e.code == 429:
                raise Exception(last_error)
            # 其他 HTTP 错误重试
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # 指数退避
                continue
            raise Exception(last_error)
        except urllib.error.URLError as e:
            last_error = f"网络错误: {e.reason}"
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)
                continue
            raise Exception(last_error)
        except Exception as e:
            last_error = f"请求错误: {e}"
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)
                continue
            raise Exception(last_error)
    
    # 提取响应内容
    choice = resp_data.get('choices', [{}])[0]
    content = choice.get('message', {}).get('content', '')
    finish_reason = choice.get('finish_reason', '')
    
    # 检查是否被截断
    if finish_reason == 'length':
        print(f"⚠️ 警告: LLM 输出被截断 (finish_reason=length)")
    
    # 记录 token 使用情况
    usage = resp_data.get('usage', {})
    if usage:
        print(f"Token 使用: prompt={usage.get('prompt_tokens', 0)}, completion={usage.get('completion_tokens', 0)}, total={usage.get('total_tokens', 0)}")
    
    if not content:
        raise Exception("LLM 返回空内容")
    
    # 解析 JSON
    try:
        result = json.loads(content)
        # 记录解析出的 Label 数量
        labels_count = len(result.get('labels', []))
        print(f"LLM 返回 {labels_count} 个 Labels")
        return result
    except json.JSONDecodeError as e:
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            result = json.loads(json_match.group(1))
            labels_count = len(result.get('labels', []))
            print(f"LLM 返回 {labels_count} 个 Labels (从代码块提取)")
            return result
        raise Exception(f"JSON 解析失败: {e}")


def _fallback_parse(preparsed_labels: Optional[List[Dict]]) -> Dict[str, Any]:
    """LLM 不可用时的回退解析
    
    Args:
        preparsed_labels: 预解析的 Labels
    
    Returns:
        基于预解析结果的配置
    """
    labels = []
    seen_labels = set()  # 用于去重
    
    if preparsed_labels:
        for label in preparsed_labels:
            label_oct = label.get('label_oct', '')
            
            # 跳过无效或重复的 Label
            if not label_oct or label_oct in seen_labels:
                continue
            seen_labels.add(label_oct)
            
            # 如果没有名称，从原始行数据尝试提取或生成默认名称
            name = label.get('name', '')
            if not name:
                raw_row = label.get('_raw_row', [])
                # 尝试从原始行中找到非数字、非空的文本作为名称
                for cell in raw_row:
                    if cell and isinstance(cell, str) and not cell.isdigit():
                        cell_clean = cell.strip()
                        if len(cell_clean) > 2 and cell_clean not in ['数据内容', '标   号', '更新速率']:
                            name = cell_clean
                            break
                # 如果还是没有，使用默认名称
                if not name:
                    name = f'Label_{label_oct}'
            
            # 清理并构建 Label
            clean_label = {
                'label_oct': label_oct,
                'name': name,
                'direction': label.get('direction', ''),
                'sources': label.get('sources', []),
                'discrete_bits': label.get('discrete_bits', {}),
                'special_fields': label.get('special_fields', []),
                'bnr_fields': label.get('bnr_fields', []),
                'notes': label.get('notes', '预解析生成，需人工补充位定义')
            }
            
            labels.append(clean_label)
    
    return {
        'protocol_meta': {
            'name': '待确认协议',
            'version': 'V1.0',
            'description': '由规则预解析生成，需要人工确认'
        },
        'device_info': {
            'device_name': '待确认设备',
            'system_name': '待确认系统'
        },
        'labels': labels,
        'parsing_notes': ['LLM 不可用，仅使用规则预解析结果，需要人工补充位定义']
    }


def validate_parsed_result(result: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """验证解析结果
    
    Args:
        result: 解析结果
    
    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    errors = []
    warnings = []
    
    # 检查必需字段
    if not result.get('labels'):
        errors.append("未解析出任何 Label")
        return False, errors, warnings
    
    # 检查每个 Label
    label_octs = set()
    for i, label in enumerate(result.get('labels', [])):
        prefix = f"Label[{i}]"
        
        # label_oct 必需
        label_oct = label.get('label_oct', '')
        if not label_oct:
            errors.append(f"{prefix}: 缺少 label_oct")
            continue
        
        # 验证八进制格式
        try:
            oct_val = int(label_oct, 8)
            if oct_val > 255:
                errors.append(f"{prefix}: label_oct '{label_oct}' 超出范围 (最大 377)")
        except ValueError:
            errors.append(f"{prefix}: label_oct '{label_oct}' 不是有效的八进制数")
        
        # 检查重复
        if label_oct in label_octs:
            warnings.append(f"{prefix}: label_oct '{label_oct}' 重复")
        label_octs.add(label_oct)
        
        # name 必需
        if not label.get('name'):
            warnings.append(f"{prefix}: 缺少 name")
        
        # 检查是否有有效的字段定义
        has_discrete = bool(label.get('discrete_bits'))
        has_special = bool(label.get('special_fields'))
        has_bnr = bool(label.get('bnr_fields'))
        
        if not (has_discrete or has_special or has_bnr):
            warnings.append(f"{prefix} ({label_oct}): 没有定义任何字段 (discrete_bits/special_fields/bnr_fields)")
        
        # 验证 bnr_fields
        for j, bf in enumerate(label.get('bnr_fields', [])):
            bf_prefix = f"{prefix}.bnr_fields[{j}]"
            
            data_bits = bf.get('data_bits', [])
            if len(data_bits) != 2:
                errors.append(f"{bf_prefix}: data_bits 必须是 [起始位, 结束位]")
            elif data_bits[0] > data_bits[1]:
                errors.append(f"{bf_prefix}: data_bits 起始位不能大于结束位")
            elif data_bits[0] < 1 or data_bits[1] > 32:
                errors.append(f"{bf_prefix}: data_bits 必须在 1-32 范围内")
            
            # resolution 可以为空（如时间、状态等数据不需要分辨率）
            # if bf.get('resolution') is None:
            #     warnings.append(f"{bf_prefix}: 缺少 resolution")
        
        # 验证 special_fields
        for j, sf in enumerate(label.get('special_fields', [])):
            sf_prefix = f"{prefix}.special_fields[{j}]"
            
            bits = sf.get('bits', [])
            if len(bits) != 2:
                errors.append(f"{sf_prefix}: bits 必须是 [起始位, 结束位]")
            elif bits[0] > bits[1]:
                errors.append(f"{sf_prefix}: bits 起始位不能大于结束位")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def enrich_labels_from_preparse(llm_labels: List[Dict], preparsed_labels: List[Dict]) -> List[Dict]:
    """将 LLM 结果与预解析结果合并
    
    Args:
        llm_labels: LLM 解析的 Labels
        preparsed_labels: 预解析的 Labels
    
    Returns:
        合并后的 Labels
    """
    # 建立预解析结果的索引
    preparse_map = {}
    for label in preparsed_labels:
        oct_val = label.get('label_oct', '')
        if oct_val:
            preparse_map[oct_val] = label
    
    # 合并
    enriched = []
    for label in llm_labels:
        oct_val = label.get('label_oct', '')
        preparse_label = preparse_map.get(oct_val, {})
        
        # LLM 结果优先，预解析结果补充
        enriched_label = {
            'label_oct': label.get('label_oct', preparse_label.get('label_oct', '')),
            'name': label.get('name') or preparse_label.get('name', ''),
            'direction': label.get('direction') or preparse_label.get('direction', ''),
            'sources': label.get('sources') or preparse_label.get('sources', []),
            'discrete_bits': label.get('discrete_bits') or preparse_label.get('discrete_bits', {}),
            'special_fields': label.get('special_fields') or preparse_label.get('special_fields', []),
            'bnr_fields': label.get('bnr_fields') or preparse_label.get('bnr_fields', []),
            'notes': label.get('notes') or preparse_label.get('notes', '')
        }
        
        # 保留置信度信息
        if '_confidence' in label:
            enriched_label['_confidence'] = label['_confidence']
        elif '_confidence' in preparse_label:
            enriched_label['_confidence'] = preparse_label['_confidence']
        
        enriched.append(enriched_label)
    
    return enriched


if __name__ == '__main__':
    # 测试
    print("LLM Parser 模块")
    print(f"API Base URL: {LLM_API_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    print(f"API Key 已配置: {'是' if LLM_API_KEY else '否'}")
