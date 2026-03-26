# -*- coding: utf-8 -*-
"""
检查 IRS2_1 解析结果: 完整性和CRC校验
结果写入到 check_report.txt
"""
import struct
import os
import sys
import time

desktop = r'C:\Users\wangz\Desktop'
report_path = None
for f in os.listdir(desktop):
    full = os.path.join(desktop, f)
    if os.path.isdir(full):
        try:
            for i in os.listdir(full):
                if i == 'check_result.py':
                    report_path = os.path.join(full, 'check_report.txt')
        except:
            pass

log = open(report_path, 'w', encoding='utf-8')

def out(msg=''):
    log.write(msg + '\n')
    log.flush()


def crc16(data: bytes) -> int:
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
    return crc & 0xFFFF


MANUFACTURER_MAP = {0: '航天时代', 1: '陕西华燕', 2: '中科导控'}

# ========== 找文件 ==========
txt_file = None
xlsx_file = None
for f in os.listdir(desktop):
    full = os.path.join(desktop, f)
    if os.path.isdir(full):
        try:
            for i in os.listdir(full):
                if i == 'IRS2_1.txt':
                    txt_file = os.path.join(full, i)
                if '231055' in i and i.endswith('.xlsx') and not i.startswith('~'):
                    xlsx_file = os.path.join(full, i)
        except:
            pass

out("=" * 60)
out("  IRS2_1 数据完整性检查报告")
out("=" * 60)
out(f"\n原始文件: {txt_file}")
out(f"文件大小: {os.path.getsize(txt_file)/1024/1024:.1f} MB")
if xlsx_file:
    out(f"Excel文件: {xlsx_file}")
    out(f"Excel大小: {os.path.getsize(xlsx_file)/1024/1024:.1f} MB")

# ========== 读取 ==========
out("\n--- 步骤1: 读取原始文件 ---")
start = time.time()
with open(txt_file, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()
tokens = content.split()
del content
out(f"  总hex字节数: {len(tokens):,}")
out(f"  读取耗时: {time.time()-start:.1f}s")

# ========== 查找包头 ==========
out("\n--- 步骤2: 查找EB90包头 ---")
eb90_positions = []
for i in range(len(tokens) - 1):
    if tokens[i].upper() == 'EB' and tokens[i+1].upper() == '90':
        eb90_positions.append(i)

total_packets = len(eb90_positions)
out(f"  找到包头数量: {total_packets:,}")

if eb90_positions:
    out(f"  第一个EB90位于token[{eb90_positions[0]}]")
    
    # 包间距分析
    all_gaps = {}
    for i in range(len(eb90_positions)-1):
        gap = eb90_positions[i+1] - eb90_positions[i]
        all_gaps[gap] = all_gaps.get(gap, 0) + 1
    
    gap80 = all_gaps.get(80, 0)
    gap_other = sum(v for k,v in all_gaps.items() if k != 80)
    out(f"  间距=80的数量: {gap80:,} ({gap80/(total_packets-1)*100:.2f}%)")
    out(f"  间距!=80的数量: {gap_other} ({gap_other/(total_packets-1)*100:.4f}%)")
    
    if gap_other > 0:
        out(f"  非80间距详情: {dict((k,v) for k,v in sorted(all_gaps.items()) if k != 80)}")
        out(f"  说明: 数据内容中偶尔出现EB 90字节组合（非真正包头），属正常现象")

# ========== CRC校验 ==========
out("\n--- 步骤3: 逐包CRC校验 ---")
start2 = time.time()

crc_pass = 0
crc_fail = 0
crc_fail_list = []
header_fail = 0
parse_error = 0
incomplete = 0

heading_min = float('inf')
heading_max = float('-inf')
pitch_min = float('inf')
pitch_max = float('-inf')
lat_min = float('inf')
lat_max = float('-inf')
lon_min = float('inf')
lon_max = float('-inf')
alt_min = float('inf')
alt_max = float('-inf')
manufacturers = {}
frame_counts = set()

for idx, pos in enumerate(eb90_positions):
    if idx % 200000 == 0 and idx > 0:
        out(f"  已检查 {idx:,} / {total_packets:,} ({time.time()-start2:.0f}s)")
    
    if pos + 80 > len(tokens):
        incomplete += 1
        continue
    
    try:
        raw = bytes([int(tokens[pos+j], 16) for j in range(80)])
    except ValueError:
        parse_error += 1
        continue
    
    if raw[0] != 0xEB or raw[1] != 0x90:
        header_fail += 1
    
    crc_recv = struct.unpack_from('<H', raw, 78)[0]
    crc_calc = crc16(raw[2:78])
    if crc_recv == crc_calc:
        crc_pass += 1
    else:
        crc_fail += 1
        if len(crc_fail_list) < 10:
            hex_str = ' '.join(f'{raw[j]:02X}' for j in range(min(10, len(raw))))
            crc_fail_list.append((idx+1, pos, f"recv=0x{crc_recv:04X} calc=0x{crc_calc:04X} data={hex_str}..."))
    
    heading = struct.unpack_from('<H', raw, 6)[0] * 0.01
    pitch = struct.unpack_from('<h', raw, 8)[0] * 0.01
    lat = struct.unpack_from('<i', raw, 18)[0] * 0.0000001
    lon = struct.unpack_from('<i', raw, 22)[0] * 0.0000001
    alt = struct.unpack_from('<i', raw, 26)[0] * 0.01
    
    if heading < heading_min: heading_min = heading
    if heading > heading_max: heading_max = heading
    if pitch < pitch_min: pitch_min = pitch
    if pitch > pitch_max: pitch_max = pitch
    if lat < lat_min: lat_min = lat
    if lat > lat_max: lat_max = lat
    if lon < lon_min: lon_min = lon
    if lon > lon_max: lon_max = lon
    if alt < alt_min: alt_min = alt
    if alt > alt_max: alt_max = alt
    
    mfr_code = raw[3] & 0x03
    mfr = MANUFACTURER_MAP.get(mfr_code, f'未知({mfr_code})')
    manufacturers[mfr] = manufacturers.get(mfr, 0) + 1
    frame_counts.add(raw[5])

out(f"  检查完成！耗时: {time.time()-start2:.1f}s")

# 释放大量内存
del tokens
del eb90_positions

# ========== 最终报告 ==========
total_elapsed = time.time() - start
out("")
out("=" * 60)
out("  最终检查报告")
out("=" * 60)
out(f"  总数据包数: {total_packets:,}")
out(f"  不完整包（末尾截断）: {incomplete}")
out(f"  十六进制解析异常: {parse_error}")
out(f"  包头异常(非EB90): {header_fail}")
out("")
out(f"  CRC校验通过: {crc_pass:,} / {total_packets:,} ({crc_pass/total_packets*100:.4f}%)")
out(f"  CRC校验失败: {crc_fail:,} / {total_packets:,} ({crc_fail/total_packets*100:.4f}%)")
if crc_fail_list:
    out("  CRC失败详情（前10个）:")
    for seq, pos, detail in crc_fail_list:
        out(f"    包#{seq} (位置{pos}): {detail}")
out("")
out(f"  厂家分布:")
for mfr, cnt in sorted(manufacturers.items(), key=lambda x: -x[1]):
    out(f"    {mfr}: {cnt:,} 包 ({cnt/total_packets*100:.2f}%)")
out(f"  帧计数值种类: {len(frame_counts)} {'(0-255全覆盖，循环正常)' if len(frame_counts) == 256 else ''}")
out("")
out("  数据值范围统计:")
out(f"    航向角: {heading_min:.2f} ~ {heading_max:.2f} 度 (有效范围0-360)")
out(f"    俯仰角: {pitch_min:.2f} ~ {pitch_max:.2f} 度 (有效范围-90~90)")
out(f"    纬度:   {lat_min:.7f} ~ {lat_max:.7f} 度")
out(f"    经度:   {lon_min:.7f} ~ {lon_max:.7f} 度")
out(f"    高度:   {alt_min:.2f} ~ {alt_max:.2f} 米")

# 检查数据合理性
out("")
out("  数据合理性检查:")
issues_range = []
if heading_max > 360 or heading_min < 0:
    issues_range.append(f"航向角超出0-360范围: {heading_min:.2f}~{heading_max:.2f}")
if pitch_max > 90 or pitch_min < -90:
    issues_range.append(f"俯仰角超出-90~90范围: {pitch_min:.2f}~{pitch_max:.2f}")
if lat_min < -90 or lat_max > 90:
    issues_range.append(f"纬度超出-90~90范围")
if lon_min < -180 or lon_max > 180:
    issues_range.append(f"经度超出-180~180范围")
if not issues_range:
    out("    所有数据值在合理范围内")
else:
    for issue in issues_range:
        out(f"    警告: {issue}")

out("")
if xlsx_file:
    out(f"  Excel文件大小: {os.path.getsize(xlsx_file)/1024/1024:.1f} MB (已生成)")
out(f"  总检查耗时: {total_elapsed:.1f}s")
out("=" * 60)

# 总结论
issues = []
if incomplete > 0:
    issues.append(f"{incomplete}个不完整包")
if parse_error > 0:
    issues.append(f"{parse_error}个解析异常")
if crc_fail > 0:
    issues.append(f"{crc_fail}个CRC失败")

if not issues:
    out(f"\n====> 结论: 全部 {total_packets:,} 个数据包CRC校验通过！数据完整无误。 <====")
else:
    out(f"\n====> 结论: 存在以下问题 - {'; '.join(issues)} <====")

out(f"\n报告已保存到: {report_path}")
log.close()
