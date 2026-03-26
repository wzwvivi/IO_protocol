# -*- coding: utf-8 -*-
"""查看 32-3 设备的 Label 数据结构"""
import sqlite3
import json
import os

def main():
    db_path = os.environ.get('DB_PATH', '/app/data/arinc429.db')
    if not os.path.exists(db_path):
        db_path = 'data/arinc429.db'
    
    print(f"数据库路径: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 先查看 devices 表结构
    cursor.execute("PRAGMA table_info(devices)")
    columns = cursor.fetchall()
    print("devices 表结构:")
    col_names = []
    for col in columns:
        print(f"  {col['name']} ({col['type']})")
        col_names.append(col['name'])
    
    # 根据实际列名查找 32-3 设备
    if 'full_name' in col_names:
        cursor.execute("SELECT * FROM devices WHERE full_name LIKE '%32-3%'")
    elif 'name' in col_names:
        cursor.execute("SELECT * FROM devices WHERE name LIKE '%32-3%'")
    devices = cursor.fetchall()
    
    print(f"\n找到 {len(devices)} 个 32-3 相关设备:")
    for d in devices:
        # 打印所有列
        print(f"  {dict(d)}")
    
    if not devices:
        print("没有找到 32-3 设备")
        return
    
    device_id = devices[0]['id']
    
    # 查询 Labels
    cursor.execute("""
        SELECT id, label_oct, name, direction, sources, 
               discrete_bits, special_fields, bnr_fields, notes
        FROM labels 
        WHERE device_id = ?
        ORDER BY label_oct
    """, (device_id,))
    
    labels = cursor.fetchall()
    print(f"\n32-3 设备共有 {len(labels)} 个 Label:")
    print("=" * 80)
    
    for label in labels[:5]:  # 只显示前 5 个
        print(f"\n--- Label {label['label_oct']} ---")
        print(f"  name: {label['name']}")
        print(f"  direction: {label['direction']}")
        print(f"  sources: {label['sources']}")
        
        # 解析 JSON 字段
        discrete_bits = json.loads(label['discrete_bits']) if label['discrete_bits'] else {}
        special_fields = json.loads(label['special_fields']) if label['special_fields'] else []
        bnr_fields = json.loads(label['bnr_fields']) if label['bnr_fields'] else []
        
        print(f"  discrete_bits: {json.dumps(discrete_bits, ensure_ascii=False)}")
        print(f"  special_fields: {json.dumps(special_fields, ensure_ascii=False)}")
        print(f"  bnr_fields: {json.dumps(bnr_fields, ensure_ascii=False, indent=4)}")
        print(f"  notes: {label['notes']}")
    
    if len(labels) > 5:
        print(f"\n... 还有 {len(labels) - 5} 个 Label")
    
    # 统计字段使用情况
    print("\n" + "=" * 80)
    print("字段使用统计:")
    
    has_bnr = 0
    has_discrete = 0
    has_special = 0
    
    for label in labels:
        discrete_bits = json.loads(label['discrete_bits']) if label['discrete_bits'] else {}
        special_fields = json.loads(label['special_fields']) if label['special_fields'] else []
        bnr_fields = json.loads(label['bnr_fields']) if label['bnr_fields'] else []
        
        if bnr_fields:
            has_bnr += 1
        if discrete_bits:
            has_discrete += 1
        if special_fields:
            has_special += 1
    
    print(f"  有 bnr_fields 的 Label: {has_bnr}/{len(labels)}")
    print(f"  有 discrete_bits 的 Label: {has_discrete}/{len(labels)}")
    print(f"  有 special_fields 的 Label: {has_special}/{len(labels)}")
    
    conn.close()

if __name__ == '__main__':
    main()
