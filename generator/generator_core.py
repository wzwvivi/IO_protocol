# -*- coding: utf-8 -*-
"""
ARINC429 代码生成器核心模块
根据协议配置生成 Python 解析脚本

更新: 支持统一的字段定义格式
- discrete_bits: 单bit离散信号
- special_fields: 多bit枚举字段
- bnr_fields: 数值字段 (BNR)
"""

import json
import copy
from datetime import datetime
from jinja2 import Environment, BaseLoader


def validate_config(config, labels=None, skip_empty_labels=False):
    """验证协议配置的完整性和正确性
    
    支持新旧两种格式：
    - 旧格式: { protocol_meta, labels }
    - 新格式: { protocol_meta, device_tree } (labels 作为参数传入)
    
    Args:
        config: 协议配置字典
        labels: 可选，直接传入 labels 列表（用于新格式）
        skip_empty_labels: 如果为 True，跳过空 label_oct 的 Label 而不是报错
    Returns:
        错误列表 (空列表表示验证通过)
    """
    errors = []
    warnings = []
    
    # 检查必需字段
    if not config.get('protocol_meta'):
        errors.append('缺少 protocol_meta 字段')
    else:
        meta = config['protocol_meta']
        if not meta.get('name'):
            errors.append('protocol_meta.name 不能为空')
        if not meta.get('version'):
            errors.append('protocol_meta.version 不能为空')
    
    # 获取 labels：优先使用传入的参数，其次从配置中获取
    if labels is None:
        labels = config.get('labels', [])
    
    if not labels:
        errors.append('缺少 labels 字段或 labels 为空')
        return errors
    
    if not isinstance(labels, list) or len(labels) == 0:
        errors.append('labels 必须是非空数组')
        return errors
    
    # 检查每个 Label 定义
    label_octs = set()
    for i, label in enumerate(labels):
        prefix = f'labels[{i}]'
        
        # 必需字段 - label_oct
        if not label.get('label_oct'):
            if skip_empty_labels:
                warnings.append(f'{prefix}: label_oct 为空，已跳过')
                continue
            else:
                errors.append(f'{prefix}: label_oct 不能为空')
        else:
            # 检查八进制格式
            try:
                oct_val = int(label['label_oct'], 8)
                if oct_val > 255:
                    errors.append(f'{prefix}: label_oct "{label["label_oct"]}" 超出范围 (最大377)')
                if label['label_oct'] in label_octs:
                    errors.append(f'{prefix}: label_oct "{label["label_oct"]}" 重复')
                label_octs.add(label['label_oct'])
            except ValueError:
                errors.append(f'{prefix}: label_oct "{label["label_oct"]}" 不是有效的八进制数')
        
        if not label.get('name'):
            errors.append(f'{prefix}: name 不能为空')
        
        # 检查是否至少有一种字段定义（改为警告，不阻止生成）
        has_discrete = bool(label.get('discrete_bits'))
        has_special = bool(label.get('special_fields'))
        has_bnr = bool(label.get('bnr_fields'))
        
        # 允许没有字段定义的 Label（只有基本信息）
        # if not (has_discrete or has_special or has_bnr):
        #     warnings.append(f'{prefix}: 没有定义任何字段，将只包含基本信息')
        
        # 检查 bnr_fields 格式（放宽验证，允许空值使用默认值）
        for j, bf in enumerate(label.get('bnr_fields', [])):
            bf_prefix = f'{prefix}.bnr_fields[{j}]'
            if not bf.get('name'):
                errors.append(f'{bf_prefix}: name 不能为空')
            if not bf.get('data_bits') or len(bf.get('data_bits', [])) != 2:
                errors.append(f'{bf_prefix}: data_bits 必须是 [起始位, 结束位]')
            # resolution 为空时使用默认值 1，不再报错
            # if bf.get('resolution') is None:
            #     errors.append(f'{bf_prefix}: resolution 不能为空')
    
    return errors


# Jinja2 模板 - 生成的 Python 解析脚本
# 注意：所有字符串值使用 pystr 过滤器进行安全转义
PARSER_TEMPLATE = '''# -*- coding: utf-8 -*-
"""
{{ protocol_name }} - ARINC429 解析脚本
版本: {{ protocol_version }}
{{ protocol_description }}

自动生成时间: {{ generated_at }}
"""

import sys
import os
from datetime import datetime

# 导入 ARINC429 运行时模块
# 确保 arinc429_runtime.py 在同一目录或 Python 路径中
try:
    from arinc429_runtime import (
        reverse_bits_8, extract_label, extract_bit, extract_bits,
        check_odd_parity, decode_ssm, decode_ssm_by_type, decode_bnr_signed, decode_bnr_unsigned,
        decode_bcd_field, interpret_discrete_desc, parse_hex_input, load_raw_byte_file,
        create_excel_workbook, write_excel_row, finalize_excel
    )
except ImportError:
    print("错误: 找不到 arinc429_runtime.py 模块")
    print("请确保该文件与本脚本在同一目录下")
    sys.exit(1)


# ============================================================
# 协议定义 - {{ protocol_name }}
# ============================================================
{% for label in labels %}

LABEL_{{ label.label_oct }} = {
    'label_oct': '{{ label.label_oct }}',
    'label_dec': {{ label.label_dec }},  # 八进制 {{ label.label_oct }}
    'name': {{ label.name | default("Unknown", true) | pystr }},
    'direction': {{ label.direction | default("", true) | pystr }},
    'sources': {{ label.sources | tojson }},
    'sdi': {{ label.sdi | default('None', true) }},  # SDI 过滤 (None=不过滤, 0-3=指定SDI)
    'ssm_type': {{ label.ssm_type | default("'bnr'", true) }},  # SSM 解释类型: 'bnr', 'discrete', 'bcd'
{% if label.bnr_fields %}
    # 数值字段 (BNR/BCD)
    'bnr_fields': [
{% for bf in label.bnr_fields %}
        {
            'name': {{ bf.name | default("BNR_Value", true) | pystr }},
            'data_bits': ({{ bf.data_bits[0] | default(11, true) }}, {{ bf.data_bits[1] | default(29, true) }}),
            'encoding': {{ bf.encoding | default('bnr', true) | pystr }},  # 'bnr' 或 'bcd'
{% if bf.encoding != 'bcd' and bf.sign_bit %}
            'sign_bit': {{ bf.sign_bit }},
            'signed': True,
{% else %}
            'sign_bit': None,
            'signed': False,
{% endif %}
{% if bf.encoding == 'bcd' %}
            'resolution': 1,
{% else %}
            'resolution': {{ bf.resolution if bf.resolution is not none and bf.resolution != '' else 1 }},
{% endif %}
            'unit': {{ bf.unit | default("", true) | pystr }}
        },
{% endfor %}
    ],
{% endif %}
{% if label.discrete_bits_list %}
    # 单bit离散信号
    'discrete_bits': {
{% for bit_num, desc in label.discrete_bits_list %}
        {{ bit_num }}: {{ desc | pystr }},
{% endfor %}
    },
{% endif %}
{% if label.special_fields %}
    # 多bit字段 (枚举/uint/bcd)
    'special_fields': [
{% for sf in label.special_fields %}
        {'name': {{ sf.name | default("Field", true) | pystr }}, 'bits': ({{ sf.bits[0] | default(11, true) }}, {{ sf.bits[1] | default(29, true) }}), 'type': {{ sf.type | default('enum', true) | pystr }}{% if sf.type == 'enum' %}, 'values': {
{% for val, desc in sf.values_list %}
            {{ val }}: {{ desc | pystr }},
{% endfor %}
        }{% endif %}},
{% endfor %}
    ],
{% endif %}
    'notes': {{ label.notes | default("", true) | pystr }}
}
{% endfor %}

# ============================================================
# Label 查找表 (支持 Label+SDI 组合匹配)
# ============================================================

LABEL_LOOKUP = {}  # key: label_dec, value: label_def (无SDI区分时)
LABEL_SDI_LOOKUP = {}  # key: (label_dec, sdi), value: label_def (有SDI区分时)

for _def in [{% for label in labels %}LABEL_{{ label.label_oct }}{% if not loop.last %}, {% endif %}{% endfor %}]:
    if _def.get('sdi') is not None:
        # 有 SDI 指定时，按 (label, sdi) 组合存储
        LABEL_SDI_LOOKUP[(_def['label_dec'], _def['sdi'])] = _def
    else:
        # 无 SDI 指定时，按 label 存储
        LABEL_LOOKUP[_def['label_dec']] = _def


def find_label_def(label_dec, sdi=None):
    """查找 Label 定义，优先按 Label+SDI 匹配"""
    if sdi is not None:
        # 先尝试精确匹配 (label, sdi)
        key = (label_dec, sdi)
        if key in LABEL_SDI_LOOKUP:
            return LABEL_SDI_LOOKUP[key]
    # 回退到仅按 label 匹配
    return LABEL_LOOKUP.get(label_dec)


# ============================================================
# 核心解析函数
# ============================================================

def parse_arinc429_word(word):
    """完整解析一个32位ARINC429数据字
    
    Args:
        word: 32位整数 (bit1在最低位)
    Returns:
        dict: 解析结果
    """
    result = {}
    
    # 1. 原始数据
    result['raw_hex'] = f'0x{word:08X}'
    result['raw_bin'] = f'{word:032b}'[::-1]  # bit1在左
    
    # 2. 提取Label
    label_dec, label_oct = extract_label(word)
    result['label_dec'] = label_dec
    result['label_oct'] = label_oct
    
    # 3. 提取SDI (bits 9-10)
    sdi = extract_bits(word, 9, 10)
    result['sdi'] = sdi
    
    # 4. 提取SSM (bits 30-31)
    ssm = extract_bits(word, 30, 31)
    result['ssm_raw'] = ssm
    
    # 5. 提取奇校验位 (bit 32)
    parity_bit = extract_bit(word, 32)
    result['parity_bit'] = parity_bit
    result['parity_ok'] = check_odd_parity(word)
    
    # 6. 查找协议定义 (支持 Label+SDI 组合匹配)
    word_def = find_label_def(label_dec, sdi)
    if word_def:
        result['known'] = True
        result['name'] = word_def['name']
        result['direction'] = word_def['direction']
        result['sources'] = word_def['sources']
        result['notes'] = word_def.get('notes', '')
        
        # 根据信号类型解释 SSM
        ssm_type = word_def.get('ssm_type', 'bnr')
        result['ssm_desc'] = decode_ssm_by_type(ssm, ssm_type)
        
        # 7. 解析数值字段 (BNR/BCD)
        bnr_results = []
        for bf in word_def.get('bnr_fields', []):
            ds, de = bf['data_bits']
            encoding = bf.get('encoding', 'bnr')
            
            if encoding == 'bcd':
                # BCD 解码
                data_raw = extract_bits(word, ds, de)
                bcd_val = decode_bcd_field(data_raw, de - ds + 1)
                bnr_results.append({
                    'name': bf['name'],
                    'data_bits': f'bit{ds}-bit{de}',
                    'data_raw': data_raw,
                    'encoding': 'bcd',
                    'sign': None,
                    'physical_value': bcd_val,
                    'unit': bf.get('unit', ''),
                    'resolution': 1
                })
            elif bf.get('signed') and bf.get('sign_bit'):
                # BNR 有符号
                res = bf['resolution']
                sb = bf['sign_bit']
                data_raw, sign, phys_val = decode_bnr_signed(word, ds, de, sb, res)
                bnr_results.append({
                    'name': bf['name'],
                    'data_bits': f'bit{ds}-bit{de}',
                    'data_raw': data_raw,
                    'encoding': 'bnr',
                    'sign': sign,
                    'sign_desc': '正' if sign == 0 else '负',
                    'physical_value': phys_val,
                    'unit': bf.get('unit', ''),
                    'resolution': res
                })
            else:
                # BNR 无符号
                res = bf['resolution']
                data_raw, phys_val = decode_bnr_unsigned(word, ds, de, res)
                bnr_results.append({
                    'name': bf['name'],
                    'data_bits': f'bit{ds}-bit{de}',
                    'data_raw': data_raw,
                    'encoding': 'bnr',
                    'sign': None,
                    'physical_value': phys_val,
                    'unit': bf.get('unit', ''),
                    'resolution': res
                })
        result['bnr_fields'] = bnr_results
        
        # 如果只有一个BNR字段，也设置顶层物理值（兼容旧格式）
        if len(bnr_results) == 1:
            result['physical_value'] = bnr_results[0]['physical_value']
            result['data_raw'] = bnr_results[0]['data_raw']
            result['sign'] = bnr_results[0]['sign']
            result['sign_desc'] = bnr_results[0].get('sign_desc', '')
            result['unit'] = bnr_results[0]['unit']
            result['resolution'] = bnr_results[0]['resolution']
            result['data_bits_range'] = bnr_results[0]['data_bits']
        
        # 8. 解码各离散位
        discrete_results = []
        if 'discrete_bits' in word_def:
            for bit_num, desc in sorted(word_def['discrete_bits'].items()):
                bit_val = extract_bit(word, bit_num)
                discrete_results.append({
                    'bit': bit_num,
                    'value': bit_val,
                    'description': desc
                })
        result['discrete_bits'] = discrete_results
        
        # 9. 解码特殊多位字段 (支持 enum/uint/bcd)
        special_results = []
        if 'special_fields' in word_def:
            for sf in word_def['special_fields']:
                bs, be = sf['bits']
                field_val = extract_bits(word, bs, be)
                field_type = sf.get('type', 'enum')
                
                if field_type == 'bcd':
                    # BCD 解码：每4位表示一个十进制数字
                    bcd_val = decode_bcd_field(field_val, be - bs + 1)
                    special_results.append({
                        'name': sf['name'],
                        'bits': f'bit{bs}-bit{be}',
                        'raw_value': field_val,
                        'bcd_value': bcd_val,
                        'description': str(bcd_val),
                        'type': 'bcd'
                    })
                elif field_type == 'uint':
                    special_results.append({
                        'name': sf['name'],
                        'bits': f'bit{bs}-bit{be}',
                        'raw_value': field_val,
                        'description': str(field_val),
                        'type': 'uint'
                    })
                else:  # enum
                    values = sf.get('values', {})
                    val_desc = values.get(field_val, f'未定义({field_val})')
                    special_results.append({
                        'name': sf['name'],
                        'bits': f'bit{bs}-bit{be}',
                        'raw_value': field_val,
                        'description': val_desc,
                        'type': 'enum'
                    })
        result['special_fields'] = special_results
    else:
        result['known'] = False
        result['name'] = f'未知Label ({label_oct} oct)'
        result['ssm_desc'] = decode_ssm(ssm)  # 未知 Label 使用默认 SSM 解释
        all_bits = {}
        for i in range(1, 33):
            all_bits[i] = extract_bit(word, i)
        result['all_bits'] = all_bits
    
    return result


def format_parse_result(result):
    """将解析结果格式化为可读字符串"""
    lines = []
    lines.append('=' * 60)
    lines.append(f'ARINC429 数据字解析结果')
    lines.append('=' * 60)
    lines.append(f'原始数据 (HEX): {result["raw_hex"]}')
    lines.append(f'原始数据 (BIN): {result["raw_bin"]}')
    lines.append(f'')
    lines.append(f'--- 标签 (Label) ---')
    lines.append(f'  Label (八进制): {result["label_oct"]}')
    lines.append(f'  Label (十进制): {result["label_dec"]}')
    lines.append(f'')
    lines.append(f'--- SDI (Bits 9-10) ---')
    lines.append(f'  SDI: {result["sdi"]:02b} ({result["sdi"]})')
    lines.append(f'')
    lines.append(f'--- 状态矩阵 SSM (Bits 30-31) ---')
    lines.append(f'  SSM: {result["ssm_raw"]:02b} -> {result["ssm_desc"]}')
    lines.append(f'')
    lines.append(f'--- 奇校验 (Bit 32) ---')
    lines.append(f'  校验位: {result["parity_bit"]}')
    lines.append(f'  校验结果: {"通过" if result["parity_ok"] else "失败"}')
    lines.append(f'')
    
    if result['known']:
        lines.append(f'--- 信号识别 ---')
        lines.append(f'  信号名称: {result["name"]}')
        lines.append(f'  方向: {result["direction"]}')
        lines.append(f'  可能来源: {", ".join(result["sources"])}')
        if result.get('notes'):
            lines.append(f'  备注: {result["notes"]}')
        lines.append(f'')
        
        # 数值字段 (BNR/BCD)
        if result.get('bnr_fields'):
            lines.append(f'--- 数值字段 ---')
            for bf in result['bnr_fields']:
                encoding = bf.get('encoding', 'bnr').upper()
                lines.append(f'  [{bf["name"]}] ({encoding})')
                lines.append(f'    数据位: {bf["data_bits"]}')
                lines.append(f'    原始值: {bf["data_raw"]} (0x{bf["data_raw"]:X})')
                if bf.get('encoding') == 'bcd':
                    lines.append(f'    BCD值: {bf["physical_value"]} {bf["unit"]}')
                else:
                    if bf.get('sign') is not None:
                        lines.append(f'    符号: {bf["sign"]} ({bf["sign_desc"]})')
                    lines.append(f'    分辨率: {bf["resolution"]}')
                    lines.append(f'    物理值: {bf["physical_value"]:.6f} {bf["unit"]}')
        
        # 离散位
        if result.get('discrete_bits'):
            lines.append(f'--- 离散位解析 ---')
            for db in result['discrete_bits']:
                field_name, interp = interpret_discrete_desc(db['description'], db['value'])
                lines.append(f'  Bit {db["bit"]}: {db["value"]} -> [{field_name}] {interp}')
        
        # 特殊字段
        if result.get('special_fields'):
            lines.append(f'--- 多位枚举字段 ---')
            for sf in result['special_fields']:
                lines.append(f'  {sf["name"]} ({sf["bits"]}): {sf["raw_value"]} -> {sf["description"]}')
    else:
        lines.append(f'--- 未识别的Label ---')
        lines.append(f'  此Label未在协议中定义')
    
    lines.append('=' * 60)
    return '\\n'.join(lines)


def parse_batch_to_excel(words, output_path=None):
    """批量解析ARINC429字并输出到Excel"""
    if output_path is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, f'ARINC429_解析结果_{ts}.xlsx')
    
    wb, ws, headers = create_excel_workbook()
    
    for idx, word in enumerate(words, 1):
        result = parse_arinc429_word(word)
        write_excel_row(ws, idx + 1, result, word, LABEL_LOOKUP)
    
    finalize_excel(wb, ws, output_path)
    return output_path


def print_all_labels():
    """打印所有已定义的Label列表"""
    print('\\n已定义的ARINC429 Label列表:')
    print('-' * 70)
    print(f'{"Label(Oct)":<12} {"名称":<25} {"方向":<15} {"字段数":<10}')
    print('-' * 70)
    
    sorted_defs = sorted(LABEL_LOOKUP.values(), key=lambda x: x['label_dec'])
    for d in sorted_defs:
        field_count = len(d.get('bnr_fields', [])) + len(d.get('discrete_bits', {})) + len(d.get('special_fields', []))
        print(f'{d["label_oct"]:<12} {d["name"]:<25} {d["direction"]:<15} {field_count:<10}')
    print('-' * 70)


def interactive_mode():
    """交互式解析模式"""
    print('=' * 60)
    print('{{ protocol_name }} - ARINC429 解析器')
    print('版本: {{ protocol_version }}')
    print('=' * 60)
    print()
    print('使用方法:')
    print('  输入32位HEX: 67FF00B2 或 0x67FF00B2')
    print('  输入4字节:   B2 00 FF 67 (小端序, Label字节在前)')
    print('  输入 "list" 查看所有已定义的Label')
    print('  输入 "quit" 或 "exit" 退出')
    print('  输入 "file <路径>" 从文件批量解析')
    print('  输入 "raw <路径>"  从原始字节文件解析')
    print()
    
    while True:
        try:
            user_input = input('请输入ARINC429数据字 (hex): ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\\n退出.')
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ('quit', 'exit', 'q'):
            print('退出.')
            break
        
        if user_input.lower() == 'list':
            print_all_labels()
            continue
        
        if user_input.lower().startswith('raw '):
            filepath = user_input[4:].strip()
            if os.path.exists(filepath):
                print(f'正在从原始字节文件读取: {filepath}')
                words = load_raw_byte_file(filepath)
                if words:
                    print(f'读取到 {len(words)} 个数据字, 正在解析...')
                    out = parse_batch_to_excel(words)
                    print(f'结果已保存到: {out}')
                else:
                    print('文件中没有有效数据')
            else:
                print(f'文件不存在: {filepath}')
            continue
        
        if user_input.lower().startswith('file '):
            filepath = user_input[5:].strip()
            if os.path.exists(filepath):
                print(f'正在从文件读取: {filepath}')
                words = []
                with open(filepath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            try:
                                words.append(parse_hex_input(line))
                            except ValueError:
                                print(f'  跳过无效行: {line}')
                if words:
                    print(f'读取到 {len(words)} 个数据字, 正在解析...')
                    out = parse_batch_to_excel(words)
                    print(f'结果已保存到: {out}')
                else:
                    print('文件中没有有效数据')
            else:
                print(f'文件不存在: {filepath}')
            continue
        
        # 尝试解析hex输入
        try:
            word = parse_hex_input(user_input)
            result = parse_arinc429_word(word)
            print(format_parse_result(result))
        except ValueError as e:
            print(f'输入格式错误: {e}')
            print('请输入有效的32位十六进制数 (如: 67FF00B2 或 B2 00 FF 67)')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == '--list':
            print_all_labels()
        elif arg == '--raw' and len(sys.argv) > 2:
            filepath = sys.argv[2]
            if os.path.exists(filepath):
                words = load_raw_byte_file(filepath)
                if words:
                    print(f'从原始文件读取到 {len(words)} 个ARINC429数据字')
                    out = parse_batch_to_excel(words)
                    print(f'结果已保存到: {out}')
            else:
                print(f'文件不存在: {filepath}')
        elif arg == '--file' and len(sys.argv) > 2:
            filepath = sys.argv[2]
            if os.path.exists(filepath):
                words = []
                with open(filepath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            try:
                                words.append(parse_hex_input(line))
                            except ValueError:
                                pass
                if words:
                    out = parse_batch_to_excel(words)
                    print(f'结果已保存到: {out}')
            else:
                print(f'文件不存在: {filepath}')
        elif arg == '--help':
            print('用法:')
            print('  python {{ script_name }}              # 交互模式')
            print('  python {{ script_name }} <hex>         # 解析单个数据字')
            print('  python {{ script_name }} --list        # 列出所有Label')
            print('  python {{ script_name }} --file <f>    # 从文件批量解析')
            print('  python {{ script_name }} --raw <f>     # 从原始字节文件解析')
        else:
            try:
                if len(sys.argv) == 5:
                    combined = ' '.join(sys.argv[1:5])
                    word = parse_hex_input(combined)
                else:
                    word = parse_hex_input(arg)
                result = parse_arinc429_word(word)
                print(format_parse_result(result))
            except ValueError as e:
                print(f'输入格式错误: {e}')
    else:
        interactive_mode()
'''


# ============================================================
# C 语言解析器模板 - 头文件 (.h)
# ============================================================

C_HEADER_TEMPLATE = '''/**
 * {{ protocol_name }} - ARINC429 解析器头文件
 * 版本: {{ protocol_version }}
 * {{ protocol_description }}
 * 
 * 自动生成时间: {{ generated_at }}
 */

#ifndef ARINC429_PARSER_H
#define ARINC429_PARSER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================
// 常量定义
// ============================================================

#define MAX_BNR_FIELDS 4
#define MAX_DISCRETE_BITS 16
#define MAX_SPECIAL_FIELDS 8
#define MAX_ENUM_VALUES 8

// ============================================================
// 数据类型定义
// ============================================================

typedef struct {
    const char* name;
    int data_bit_start;
    int data_bit_end;
    int encoding;       // 0=bnr, 1=bcd
    int sign_bit;       // 0 表示无符号 (仅BNR有效)
    double resolution;  // 分辨率 (仅BNR有效)
    const char* unit;
} BnrFieldDef;

typedef struct {
    int bit_num;
    const char* description;
} DiscreteBitDef;

typedef struct {
    int value;
    const char* description;
} EnumValueDef;

typedef struct {
    const char* name;
    int bit_start;
    int bit_end;
    int field_type;     // 0=uint, 1=enum, 2=bcd
    int enum_count;
    EnumValueDef enum_values[MAX_ENUM_VALUES];
} SpecialFieldDef;

typedef struct {
    const char* label_oct;
    int label_dec;
    const char* name;
    const char* direction;
    int bnr_field_count;
    BnrFieldDef bnr_fields[MAX_BNR_FIELDS];
    int discrete_bit_count;
    DiscreteBitDef discrete_bits[MAX_DISCRETE_BITS];
    int special_field_count;
    SpecialFieldDef special_fields[MAX_SPECIAL_FIELDS];
    const char* notes;
} LabelDef;

typedef struct {
    uint32_t raw_word;
    int label_dec;
    char label_oct[8];
    int sdi;
    int ssm;
    const char* ssm_desc;
    int parity_bit;
    int parity_ok;
    int known;
    const char* name;
    const char* direction;
    int bnr_count;
    struct {
        const char* name;
        int data_raw;
        int sign;
        double physical_value;
        const char* unit;
    } bnr_results[MAX_BNR_FIELDS];
    int discrete_count;
    struct {
        int bit_num;
        int value;
        const char* description;
    } discrete_results[MAX_DISCRETE_BITS];
    int special_count;
    struct {
        const char* name;
        int raw_value;
        const char* description;
        char desc_buf[32];
    } special_results[MAX_SPECIAL_FIELDS];
} ParseResult;

// ============================================================
// 函数声明
// ============================================================

// 基础工具函数
uint8_t reverse_bits_8(uint8_t byte_val);
int extract_label(uint32_t word, char* label_oct_str);
int extract_bit(uint32_t word, int bit_num);
uint32_t extract_bits(uint32_t word, int start_bit, int end_bit);
int check_odd_parity(uint32_t word);
const char* decode_ssm(int ssm_val);
const LabelDef* find_label_def(int label_dec);

// 核心解析函数
void parse_arinc429_word(uint32_t word, ParseResult* result);

// 输出函数
void print_result(const ParseResult* r);
void print_csv_header(void);
void print_csv_result(const ParseResult* r);

// 辅助函数
uint32_t bytes_to_word(uint8_t b0, uint8_t b1, uint8_t b2, uint8_t b3);

#ifdef __cplusplus
}
#endif

#endif // ARINC429_PARSER_H
'''


# ============================================================
# C 语言解析器模板 - 源文件 (.c)
# ============================================================

C_SOURCE_TEMPLATE = '''/**
 * {{ protocol_name }} - ARINC429 解析器源文件
 * 版本: {{ protocol_version }}
 * {{ protocol_description }}
 * 
 * 自动生成时间: {{ generated_at }}
 * 
 * 编译: gcc -o arinc429_parser arinc429_parser.c -lm
 * 使用: ./arinc429_parser <hex_word>
 *       ./arinc429_parser B2 00 FF 67
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "arinc429_parser.h"

// ============================================================
// Label 定义表 - {{ protocol_name }}
// ============================================================

static const LabelDef LABEL_DEFS[] = {
{%- for label in labels %}
    {
        "{{ label.label_oct }}", {{ label.label_dec }}, "{{ label.name | replace('"', '\\"') | replace('\n', ' ') }}", "{{ label.direction | default('', true) }}",
        // 数值字段 BNR/BCD ({{ label.bnr_fields | length }})
        {{ label.bnr_fields | length }}, {
{%- if label.bnr_fields %}
{%- for bf in label.bnr_fields %}
            {"{{ bf.name | replace('"', '\\"') }}", {{ bf.data_bits[0] }}, {{ bf.data_bits[1] }}, {{ 1 if bf.encoding == 'bcd' else 0 }}, {{ bf.sign_bit | default(0, true) if bf.encoding != 'bcd' else 0 }}, {{ bf.resolution | default(1, true) if bf.encoding != 'bcd' else 1 }}, "{{ bf.unit | default('', true) }}"},
{%- endfor %}
{%- else %}
            {NULL, 0, 0, 0, 0, 0, NULL}
{%- endif %}
        },
        // Discrete bits ({{ label.discrete_bits_list | length }})
        {{ label.discrete_bits_list | length }}, {
{%- if label.discrete_bits_list %}
{%- for bit_num, desc in label.discrete_bits_list %}
            { {{ bit_num }}, "{{ desc | replace('"', '\\"') | replace('\n', ' ') }}" },
{%- endfor %}
{%- else %}
            {0, NULL}
{%- endif %}
        },
        // Special fields ({{ label.special_fields | length }})
        {{ label.special_fields | length }}, {
{%- if label.special_fields %}
{%- for sf in label.special_fields %}
            {"{{ sf.name | replace('"', '\\"') }}", {{ sf.bits[0] }}, {{ sf.bits[1] }}, {{ 2 if sf.type == 'bcd' else (1 if sf.type == 'enum' else 0) }}, {{ sf.values_list | length if sf.values_list else 0 }}, {
{%- if sf.values_list %}
{%- for val, desc in sf.values_list %}
                { {{ val }}, "{{ desc | replace('"', '\\"') | replace('\n', ' ') }}" },
{%- endfor %}
{%- else %}
                {0, NULL}
{%- endif %}
            } },
{%- endfor %}
{%- else %}
            {NULL, 0, 0, 0, 0, {% raw %}{{0, NULL}}{% endraw %}}
{%- endif %}
        },
        "{{ label.notes | default('', true) | replace('"', '\\"') | replace('\n', ' ') }}"
    },
{%- endfor %}
    {NULL, 0, NULL, NULL, 0, {% raw %}{{NULL, 0, 0, 0, 0, 0, NULL}}{% endraw %}, 0, {% raw %}{{0, NULL}}{% endraw %}, 0, {% raw %}{{NULL, 0, 0, 0, 0, {{0, NULL}}}}{% endraw %}, NULL}  // 结束标记
};

// ============================================================
// 基础工具函数
// ============================================================

uint8_t reverse_bits_8(uint8_t byte_val) {
    uint8_t result = 0;
    for (int i = 0; i < 8; i++) {
        if (byte_val & (1 << i)) {
            result |= (1 << (7 - i));
        }
    }
    return result;
}

int extract_label(uint32_t word, char* label_oct_str) {
    uint8_t raw = word & 0xFF;
    int label_val = reverse_bits_8(raw);
    sprintf(label_oct_str, "%o", label_val);
    return label_val;
}

int extract_bit(uint32_t word, int bit_num) {
    return (word >> (bit_num - 1)) & 1;
}

uint32_t extract_bits(uint32_t word, int start_bit, int end_bit) {
    int num_bits = end_bit - start_bit + 1;
    uint32_t mask = (1U << num_bits) - 1;
    return (word >> (start_bit - 1)) & mask;
}

int check_odd_parity(uint32_t word) {
    int count = 0;
    uint32_t w = word;
    while (w) {
        count += w & 1;
        w >>= 1;
    }
    return (count % 2) == 1;
}

const char* decode_ssm(int ssm_val) {
    switch (ssm_val) {
        case 0: return "00-故障";
        case 1: return "01-无效";
        case 2: return "10-测试";
        case 3: return "11-正常";
        default: return "未知";
    }
}

const LabelDef* find_label_def(int label_dec) {
    for (int i = 0; LABEL_DEFS[i].label_oct != NULL; i++) {
        if (LABEL_DEFS[i].label_dec == label_dec) {
            return &LABEL_DEFS[i];
        }
    }
    return NULL;
}

// ============================================================
// 核心解析函数
// ============================================================

void parse_arinc429_word(uint32_t word, ParseResult* result) {
    memset(result, 0, sizeof(ParseResult));
    result->raw_word = word;
    
    result->label_dec = extract_label(word, result->label_oct);
    result->sdi = extract_bits(word, 9, 10);
    result->ssm = extract_bits(word, 30, 31);
    result->ssm_desc = decode_ssm(result->ssm);
    result->parity_bit = extract_bit(word, 32);
    result->parity_ok = check_odd_parity(word);
    
    const LabelDef* def = find_label_def(result->label_dec);
    if (def) {
        result->known = 1;
        result->name = def->name;
        result->direction = def->direction;
        
        // 解析所有数值字段 (BNR/BCD)
        result->bnr_count = def->bnr_field_count;
        for (int i = 0; i < def->bnr_field_count; i++) {
            const BnrFieldDef* bf = &def->bnr_fields[i];
            int data_raw = extract_bits(word, bf->data_bit_start, bf->data_bit_end);
            int num_data_bits = bf->data_bit_end - bf->data_bit_start + 1;
            
            result->bnr_results[i].name = bf->name;
            result->bnr_results[i].data_raw = data_raw;
            result->bnr_results[i].unit = bf->unit;
            
            if (bf->encoding == 1) {
                // BCD 解码：每4位表示一个十进制数字
                int bcd_val = 0;
                int multiplier = 1;
                int num_digits = (num_data_bits + 3) / 4;
                int temp = data_raw;
                for (int d = 0; d < num_digits; d++) {
                    int digit = temp & 0x0F;
                    if (digit > 9) digit = 0;  // 无效BCD数字
                    bcd_val += digit * multiplier;
                    multiplier *= 10;
                    temp >>= 4;
                }
                result->bnr_results[i].sign = -1;
                result->bnr_results[i].physical_value = bcd_val;
            } else if (bf->sign_bit > 0) {
                // BNR 有符号
                int sign = extract_bit(word, bf->sign_bit);
                int combined = (sign << num_data_bits) | data_raw;
                int total_bits = num_data_bits + 1;
                int signed_val = sign ? (combined - (1 << total_bits)) : combined;
                
                result->bnr_results[i].sign = sign;
                result->bnr_results[i].physical_value = signed_val * bf->resolution;
            } else {
                // BNR 无符号
                result->bnr_results[i].sign = -1;
                result->bnr_results[i].physical_value = data_raw * bf->resolution;
            }
        }
        
        // 解析所有离散位
        result->discrete_count = def->discrete_bit_count;
        for (int i = 0; i < def->discrete_bit_count; i++) {
            const DiscreteBitDef* db = &def->discrete_bits[i];
            result->discrete_results[i].bit_num = db->bit_num;
            result->discrete_results[i].value = extract_bit(word, db->bit_num);
            result->discrete_results[i].description = db->description;
        }
        
        // 解析所有特殊字段 (枚举/uint/bcd)
        result->special_count = def->special_field_count;
        for (int i = 0; i < def->special_field_count; i++) {
            const SpecialFieldDef* sf = &def->special_fields[i];
            int raw_val = extract_bits(word, sf->bit_start, sf->bit_end);
            
            result->special_results[i].name = sf->name;
            result->special_results[i].raw_value = raw_val;
            result->special_results[i].description = "未定义";
            
            if (sf->field_type == 1) {
                // 枚举类型: 查找枚举值描述
                for (int j = 0; j < sf->enum_count; j++) {
                    if (sf->enum_values[j].value == raw_val) {
                        result->special_results[i].description = sf->enum_values[j].description;
                        break;
                    }
                }
            } else if (sf->field_type == 2) {
                // BCD类型: 每4位表示一个十进制数字
                int bcd_val = 0;
                int multiplier = 1;
                int num_bits = sf->bit_end - sf->bit_start + 1;
                int num_digits = (num_bits + 3) / 4;
                int temp = raw_val;
                for (int d = 0; d < num_digits; d++) {
                    int digit = temp & 0x0F;
                    if (digit > 9) digit = 0;  // 无效BCD数字
                    bcd_val += digit * multiplier;
                    multiplier *= 10;
                    temp >>= 4;
                }
                sprintf(result->special_results[i].desc_buf, "%d (BCD)", bcd_val);
                result->special_results[i].description = result->special_results[i].desc_buf;
            } else {
                // uint类型: 直接将数值转为字符串作为描述
                sprintf(result->special_results[i].desc_buf, "%d", raw_val);
                result->special_results[i].description = result->special_results[i].desc_buf;
            }
        }
    } else {
        result->known = 0;
        result->name = "未知Label";
    }
}

void print_result(const ParseResult* r) {
    printf("============================================================\\n");
    printf("ARINC429 数据字解析结果\\n");
    printf("============================================================\\n");
    printf("原始数据 (HEX): 0x%08X\\n", r->raw_word);
    printf("原始数据 (BIN): ");
    for (int i = 0; i < 32; i++) printf("%d", (r->raw_word >> i) & 1);
    printf("\\n\\n");
    
    printf("Label (八进制): %s\\n", r->label_oct);
    printf("Label (十进制): %d\\n", r->label_dec);
    printf("SDI: %d\\n", r->sdi);
    printf("SSM: %s\\n", r->ssm_desc);
    printf("奇校验: %s\\n", r->parity_ok ? "通过" : "失败");
    
    if (r->known) {
        printf("\\n信号名称: %s\\n", r->name);
        printf("方向: %s\\n", r->direction);
        
        // 打印数值字段 (BNR/BCD)
        if (r->bnr_count > 0) {
            printf("\\n--- 数值字段 ---\\n");
            for (int i = 0; i < r->bnr_count; i++) {
                printf("  [%s] 原始值: %d", r->bnr_results[i].name, r->bnr_results[i].data_raw);
                if (r->bnr_results[i].sign >= 0) {
                    printf(", 符号: %s", r->bnr_results[i].sign ? "负" : "正");
                }
                printf(", 值: %.6f %s\\n", r->bnr_results[i].physical_value, r->bnr_results[i].unit);
            }
        }
        
        // 打印离散位
        if (r->discrete_count > 0) {
            printf("\\n--- 离散位 ---\\n");
            for (int i = 0; i < r->discrete_count; i++) {
                printf("  Bit %d = %d : %s\\n", 
                       r->discrete_results[i].bit_num,
                       r->discrete_results[i].value,
                       r->discrete_results[i].description);
            }
        }
        
        // 打印特殊字段
        if (r->special_count > 0) {
            printf("\\n--- 多位枚举字段 ---\\n");
            for (int i = 0; i < r->special_count; i++) {
                printf("  [%s] 值: %d -> %s\\n",
                       r->special_results[i].name,
                       r->special_results[i].raw_value,
                       r->special_results[i].description);
            }
        }
    }
    printf("============================================================\\n\\n");
}

void print_csv_header() {
    printf("Label(Oct),Label(Dec),Name,DataType,RawValue,PhysicalValue,SSM,Parity\\n");
}

void print_csv_result(const ParseResult* r) {
    const char* data_type = "UNKNOWN";
    double phys = 0;
    int raw = 0;
    
    if (r->bnr_count > 0) {
        data_type = r->bnr_results[0].sign >= 0 ? "BNR_SIGNED" : "BNR_UNSIGNED";
        phys = r->bnr_results[0].physical_value;
        raw = r->bnr_results[0].data_raw;
    } else if (r->discrete_count > 0 || r->special_count > 0) {
        data_type = "DISCRETE";
    }
    
    printf("%s,%d,%s,%s,%d,%.6f,%s,%s\\n",
           r->label_oct, r->label_dec, r->known ? r->name : "未知",
           data_type, raw, phys, r->ssm_desc, r->parity_ok ? "通过" : "失败");
}

uint32_t bytes_to_word(uint8_t b0, uint8_t b1, uint8_t b2, uint8_t b3) {
    return (uint32_t)b0 | ((uint32_t)b1 << 8) | ((uint32_t)b2 << 16) | ((uint32_t)b3 << 24);
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        printf("{{ protocol_name }} - ARINC429 解析器\\n");
        printf("用法:\\n");
        printf("  %s <hex_word>           解析单个32位HEX\\n", argv[0]);
        printf("  %s <b0> <b1> <b2> <b3>  解析4个字节(小端序)\\n", argv[0]);
        printf("  %s --csv <bytes...>     CSV格式输出\\n", argv[0]);
        return 0;
    }
    
    int csv_mode = 0, arg_start = 1;
    if (strcmp(argv[1], "--csv") == 0) {
        csv_mode = 1;
        arg_start = 2;
        print_csv_header();
    }
    
    int i = arg_start;
    while (i < argc) {
        uint32_t word;
        if (i + 3 < argc && strlen(argv[i]) == 2) {
            uint8_t b0 = (uint8_t)strtol(argv[i], NULL, 16);
            uint8_t b1 = (uint8_t)strtol(argv[i+1], NULL, 16);
            uint8_t b2 = (uint8_t)strtol(argv[i+2], NULL, 16);
            uint8_t b3 = (uint8_t)strtol(argv[i+3], NULL, 16);
            word = bytes_to_word(b0, b1, b2, b3);
            i += 4;
        } else {
            word = (uint32_t)strtoul(argv[i], NULL, 16);
            i += 1;
        }
        
        ParseResult result;
        parse_arinc429_word(word, &result);
        if (csv_mode) print_csv_result(&result);
        else print_result(&result);
    }
    return 0;
}
'''


def generate_parser_code(config):
    """根据配置生成 Python 解析脚本
    
    Args:
        config: 协议配置字典
    Returns:
        生成的 Python 代码字符串
    """
    # 准备模板数据 (深拷贝避免修改原配置)
    meta = config.get('protocol_meta', {})
    raw_labels = copy.deepcopy(config.get('labels', []))
    
    # 过滤掉无效的 Labels（label_oct 为空的）
    labels = [l for l in raw_labels if l.get('label_oct')]
    
    # 预处理每个 Label
    for label in labels:
        # 计算十进制值（处理无效八进制）
        try:
            label['label_dec'] = int(label['label_oct'], 8)
        except (ValueError, TypeError):
            # 如果不是有效的八进制，尝试作为十进制处理
            try:
                label['label_dec'] = int(label['label_oct'])
            except (ValueError, TypeError):
                label['label_dec'] = 0
        
        # 确保 name 存在
        if not label.get('name'):
            label['name'] = f"Label_{label['label_oct']}"
        
        # 确保 sources 是列表
        if not label.get('sources'):
            label['sources'] = []
        elif isinstance(label['sources'], str):
            label['sources'] = [label['sources']]
        
        # 确保 bnr_fields 存在并处理默认值
        if not label.get('bnr_fields'):
            label['bnr_fields'] = []
        else:
            # 处理 bnr_fields 中的空值
            for bf in label['bnr_fields']:
                # resolution 为空时使用默认值 1
                if bf.get('resolution') is None or bf.get('resolution') == '':
                    bf['resolution'] = 1
                else:
                    try:
                        bf['resolution'] = float(bf['resolution'])
                    except (ValueError, TypeError):
                        bf['resolution'] = 1
                
                # data_bits 确保存在
                if not bf.get('data_bits') or len(bf.get('data_bits', [])) < 2:
                    bf['data_bits'] = [11, 29]
                
                # unit 确保存在
                if not bf.get('unit'):
                    bf['unit'] = ''
        
        # 将 discrete_bits 的字符串键转为整数键，并转为列表便于模板迭代
        if label.get('discrete_bits'):
            discrete_list = []
            for k, v in label['discrete_bits'].items():
                discrete_list.append((int(k), v))
            discrete_list.sort(key=lambda x: x[0])
            label['discrete_bits_list'] = discrete_list
        else:
            label['discrete_bits_list'] = []
        
        # 处理 special_fields 中的 values 和 bits
        if label.get('special_fields'):
            for sf in label['special_fields']:
                # 确保 bits 存在
                if not sf.get('bits') or len(sf.get('bits', [])) < 2:
                    sf['bits'] = [11, 29]
                
                # 确保 name 存在
                if not sf.get('name'):
                    sf['name'] = 'Field'
                
                if sf.get('values'):
                    values_list = []
                    for k, v in sf['values'].items():
                        values_list.append((int(k), v))
                    values_list.sort(key=lambda x: x[0])
                    sf['values_list'] = values_list
                else:
                    sf['values_list'] = []
        else:
            label['special_fields'] = []
    
    # 创建 Jinja2 环境
    env = Environment(loader=BaseLoader())
    
    # 添加 Python 字符串安全转义过滤器
    def pystr_filter(value):
        """将值转为安全的 Python 字符串字面量"""
        if value is None:
            return "''"
        s = str(value)
        # 转义反斜杠、单引号、换行等
        s = s.replace('\\', '\\\\')
        s = s.replace("'", "\\'")
        s = s.replace('\n', '\\n')
        s = s.replace('\r', '\\r')
        s = s.replace('\t', '\\t')
        return f"'{s}'"
    
    env.filters['pystr'] = pystr_filter
    template = env.from_string(PARSER_TEMPLATE)
    
    # 渲染模板
    code = template.render(
        protocol_name=meta.get('name', 'ARINC429 Protocol'),
        protocol_version=meta.get('version', '1.0'),
        protocol_description=meta.get('description', ''),
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        script_name=f"{meta.get('name', 'protocol')}_parser.py",
        labels=labels
    )
    
    return code


def _preprocess_labels_for_c(raw_labels):
    """预处理 Labels 用于 C 代码生成
    
    处理各种可能的数据格式问题，确保生成的 C 代码能正确编译
    """
    # 过滤掉无效的 Labels（label_oct 为空的）
    labels = [l for l in raw_labels if l.get('label_oct')]
    
    for label in labels:
        # 转换八进制 Label 为十进制
        try:
            label['label_dec'] = int(label['label_oct'], 8)
        except (ValueError, TypeError):
            label['label_dec'] = 0
        
        # 确保基本字段存在
        if not label.get('sources'):
            label['sources'] = []
        if not label.get('notes'):
            label['notes'] = ''
        if not label.get('name'):
            label['name'] = f"Label_{label['label_oct']}"
        if not label.get('direction'):
            label['direction'] = ''
        
        # 处理数值字段 (BNR/BCD)
        bnr_fields = label.get('bnr_fields', [])
        valid_bnr_fields = []
        for bf in bnr_fields:
            # 确保 data_bits 存在且有效
            data_bits = bf.get('data_bits', [])
            if not data_bits or len(data_bits) < 2:
                # 默认使用 11-29 位
                data_bits = [11, 29]
            
            # 获取编码类型
            encoding = bf.get('encoding', 'bnr')
            
            # 确保 resolution 是数字 (BCD 不需要)
            resolution = bf.get('resolution', 1)
            if encoding == 'bcd':
                resolution = 1
            elif resolution is None or resolution == '':
                resolution = 1
            else:
                try:
                    resolution = float(resolution)
                except (ValueError, TypeError):
                    resolution = 1.0
            
            # 确保 sign_bit 是数字或 None (BCD 不需要)
            sign_bit = 0
            if encoding != 'bcd':
                sign_bit = bf.get('sign_bit')
                if sign_bit is not None:
                    try:
                        sign_bit = int(sign_bit)
                    except (ValueError, TypeError):
                        sign_bit = 0
                else:
                    sign_bit = 0
            
            valid_bnr_fields.append({
                'name': bf.get('name', 'Value'),
                'data_bits': [int(data_bits[0]), int(data_bits[1])],
                'encoding': encoding,
                'sign_bit': sign_bit,
                'resolution': resolution,
                'unit': bf.get('unit', '')
            })
        label['bnr_fields'] = valid_bnr_fields
        
        # 将 discrete_bits 的字符串键转为整数键，并转为列表
        discrete_bits = label.get('discrete_bits', {})
        if discrete_bits and isinstance(discrete_bits, dict):
            discrete_list = []
            for k, v in discrete_bits.items():
                try:
                    bit_num = int(k)
                    # 处理描述格式：可能是 "名称:0=说明,1=说明" 或简单字符串
                    desc = str(v) if v else f'Bit_{bit_num}'
                    discrete_list.append((bit_num, desc))
                except (ValueError, TypeError):
                    continue
            discrete_list.sort(key=lambda x: x[0])
            label['discrete_bits_list'] = discrete_list
        else:
            label['discrete_bits_list'] = []
        
        # 处理 special_fields（多位枚举字段）
        special_fields = label.get('special_fields', [])
        valid_special_fields = []
        for sf in special_fields:
            # 确保 bits 存在且有效
            bits = sf.get('bits', [])
            if not bits or len(bits) < 2:
                continue  # 跳过无效的 special_field
            
            try:
                bits = [int(bits[0]), int(bits[1])]
            except (ValueError, TypeError, IndexError):
                continue
            
            # 处理 values（枚举值）
            values = sf.get('values', {})
            values_list = []
            if values and isinstance(values, dict):
                for k, v in values.items():
                    try:
                        val = int(k)
                        desc = str(v) if v else f'Value_{val}'
                        values_list.append((val, desc))
                    except (ValueError, TypeError):
                        continue
                values_list.sort(key=lambda x: x[0])
            
            valid_special_fields.append({
                'name': sf.get('name', 'Field'),
                'bits': bits,
                'type': sf.get('type', 'enum'),
                'values': values,
                'values_list': values_list
            })
        label['special_fields'] = valid_special_fields
    
    return labels


# C 代码生成的字段数量上限
C_LIMITS = {
    'MAX_BNR_FIELDS': 4,
    'MAX_DISCRETE_BITS': 16,
    'MAX_SPECIAL_FIELDS': 8,
    'MAX_ENUM_VALUES': 8
}


def validate_labels_for_c(labels):
    """验证 Labels 是否符合 C 代码生成的限制
    
    Args:
        labels: 预处理后的 Labels 列表
    Returns:
        (is_valid, errors, warnings) 元组
    """
    errors = []
    warnings = []
    
    for label in labels:
        label_id = label.get('label_oct', '???')
        label_name = label.get('name', '未命名')
        prefix = f"Label {label_id} ({label_name})"
        
        # 检查 BNR 字段数量
        bnr_count = len(label.get('bnr_fields', []))
        if bnr_count > C_LIMITS['MAX_BNR_FIELDS']:
            errors.append(f"{prefix}: BNR 字段数 {bnr_count} 超过上限 {C_LIMITS['MAX_BNR_FIELDS']}")
        
        # 检查离散位数量
        discrete_count = len(label.get('discrete_bits_list', []))
        if discrete_count > C_LIMITS['MAX_DISCRETE_BITS']:
            errors.append(f"{prefix}: 离散位数 {discrete_count} 超过上限 {C_LIMITS['MAX_DISCRETE_BITS']}")
        
        # 检查特殊字段数量
        special_count = len(label.get('special_fields', []))
        if special_count > C_LIMITS['MAX_SPECIAL_FIELDS']:
            errors.append(f"{prefix}: 特殊字段数 {special_count} 超过上限 {C_LIMITS['MAX_SPECIAL_FIELDS']}")
        
        # 检查枚举值数量
        for sf in label.get('special_fields', []):
            enum_count = len(sf.get('values_list', []))
            if enum_count > C_LIMITS['MAX_ENUM_VALUES']:
                errors.append(f"{prefix}.{sf.get('name', 'Field')}: 枚举值数 {enum_count} 超过上限 {C_LIMITS['MAX_ENUM_VALUES']}")
        
        # 检查位段合法性
        all_bits_used = set()
        
        # BNR 字段位段检查
        for bf in label.get('bnr_fields', []):
            bits = bf.get('data_bits', [])
            if len(bits) >= 2:
                start, end = bits[0], bits[1]
                if start > end:
                    errors.append(f"{prefix}.{bf.get('name', 'BNR')}: 位段起始 {start} > 结束 {end}")
                if start < 1 or end > 32:
                    errors.append(f"{prefix}.{bf.get('name', 'BNR')}: 位段 [{start}, {end}] 超出 1-32 范围")
                # 检查重叠
                for b in range(start, end + 1):
                    if b in all_bits_used:
                        warnings.append(f"{prefix}.{bf.get('name', 'BNR')}: 位 {b} 与其他字段重叠")
                    all_bits_used.add(b)
        
        # 离散位检查
        for bit_num, _ in label.get('discrete_bits_list', []):
            if bit_num < 1 or bit_num > 32:
                errors.append(f"{prefix}: 离散位 {bit_num} 超出 1-32 范围")
            if bit_num in all_bits_used:
                warnings.append(f"{prefix}: 离散位 {bit_num} 与其他字段重叠")
            all_bits_used.add(bit_num)
        
        # 特殊字段位段检查
        for sf in label.get('special_fields', []):
            bits = sf.get('bits', [])
            if len(bits) >= 2:
                start, end = bits[0], bits[1]
                if start > end:
                    errors.append(f"{prefix}.{sf.get('name', 'Field')}: 位段起始 {start} > 结束 {end}")
                if start < 1 or end > 32:
                    errors.append(f"{prefix}.{sf.get('name', 'Field')}: 位段 [{start}, {end}] 超出 1-32 范围")
                for b in range(start, end + 1):
                    if b in all_bits_used:
                        warnings.append(f"{prefix}.{sf.get('name', 'Field')}: 位 {b} 与其他字段重叠")
                    all_bits_used.add(b)
    
    return len(errors) == 0, errors, warnings


def generate_c_parser_code(config, strict=True):
    """根据配置生成 C 语言解析代码 (.h 和 .c)
    
    Args:
        config: 协议配置字典
        strict: 是否严格校验（True 时超限会抛异常）
    Returns:
        字典 {'header': str, 'source': str, 'warnings': list} 包含 .h 和 .c 代码
    Raises:
        ValueError: 当 strict=True 且校验失败时
    """
    meta = config.get('protocol_meta', {})
    raw_labels = copy.deepcopy(config.get('labels', []))
    labels = _preprocess_labels_for_c(raw_labels)
    
    # 校验字段数量和位段合法性
    is_valid, errors, warnings = validate_labels_for_c(labels)
    
    if not is_valid and strict:
        raise ValueError(f"C 代码生成校验失败:\n" + "\n".join(f"  - {e}" for e in errors))
    
    env = Environment(loader=BaseLoader())
    
    # 模板参数
    template_params = {
        'protocol_name': meta.get('name', 'ARINC429 Protocol'),
        'protocol_version': meta.get('version', '1.0'),
        'protocol_description': meta.get('description', ''),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'labels': labels
    }
    
    # 生成头文件
    header_template = env.from_string(C_HEADER_TEMPLATE)
    header_code = header_template.render(**template_params)
    
    # 生成源文件
    source_template = env.from_string(C_SOURCE_TEMPLATE)
    source_code = source_template.render(**template_params)
    
    return {
        'header': header_code,
        'source': source_code,
        'validation_errors': errors,
        'validation_warnings': warnings
    }


if __name__ == '__main__':
    # 测试: 从示例配置生成代码
    import os
    example_path = os.path.join(os.path.dirname(__file__), 'example_protocol_config.json')
    
    if os.path.exists(example_path):
        with open(example_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证配置
        errors = validate_config(config)
        if errors:
            print('配置验证失败:')
            for e in errors:
                print(f'  - {e}')
        else:
            print('配置验证通过')
            
            # 生成代码
            code = generate_parser_code(config)
            
            # 保存到文件
            output_path = os.path.join(os.path.dirname(__file__), 'output', 'test_generated_parser.py')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(code)
            print(f'Python代码已生成到: {output_path}')
            
            # 生成C代码
            c_code = generate_c_parser_code(config)
            c_output_path = os.path.join(os.path.dirname(__file__), 'output', 'test_generated_parser.c')
            with open(c_output_path, 'w', encoding='utf-8') as f:
                f.write(c_code)
            print(f'C代码已生成到: {c_output_path}')
    else:
        print(f'示例配置文件不存在: {example_path}')
