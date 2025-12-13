# -*- coding: utf-8 -*-
"""
修复CSV文件列结构的脚本
为batch_metrics.csv添加termination_reason列（如果不存在的话）
"""
import os
import csv
import shutil


def fix_csv_columns(csv_path, default_value='completed'):
    """
    修复CSV文件的列结构，确保所有行都有相同的列数
    
    Args:
        csv_path: CSV文件路径
        default_value: 为缺失列填充的默认值
    """
    if not os.path.exists(csv_path):
        print(f"文件不存在: {csv_path}")
        return False
    
    # 备份原文件
    backup_path = csv_path + '.backup'
    shutil.copy2(csv_path, backup_path)
    print(f"已备份原文件到: {backup_path}")
    
    try:
        # 读取原文件
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            print("CSV文件为空")
            return False
        
        # 检查表头
        header = rows[0]
        
        # 确定标准列顺序（包含termination_reason）
        standard_columns = [
            'batch_idx', 'start', 'end', 'processed', 'success', 'fail', 
            'missing_detail_pages', 'termination_reason', 'elapsed_seconds', 
            'insert_rate_per_sec', 'error_rate', 'timestamp'
        ]
        
        # 如果termination_reason不在表头中，需要添加
        if 'termination_reason' not in header:
            print("检测到缺少termination_reason列，正在添加...")
            
            # 在missing_detail_pages后面插入termination_reason列
            insert_index = header.index('missing_detail_pages') + 1
            header.insert(insert_index, 'termination_reason')
            
            # 为所有数据行添加默认值
            for row_idx in range(1, len(rows)):
                row = rows[row_idx]
                if len(row) < len(header):
                    row.insert(insert_index, default_value)

        
        # 写入修复后的文件
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        
        print(f"成功修复CSV文件: {csv_path}")
        print(f"表头: {header}")
        print(f"数据行数: {len(rows)-1}")
        return True
        
    except Exception as e:
        print(f"修复CSV文件时出错: {e}")
        # 恢复备份
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, csv_path)
            print("已恢复原文件")
        return False


def main():
    # 修复chengyu目录的CSV
    chengyu_csv = os.path.join(os.path.dirname(__file__), 'chengyu', 'batch_metrics.csv')
    print(f"正在修复: {chengyu_csv}")
    fix_csv_columns(chengyu_csv, default_value='completed')
    
    print()
    
    # 修复ciyu目录的CSV
    ciyu_csv = os.path.join(os.path.dirname(__file__), 'ciyu', 'batch_metrics.csv')
    print(f"正在修复: {ciyu_csv}")
    fix_csv_columns(ciyu_csv, default_value='completed')
    
    print("\n修复完成！现在可以正常使用断点续爬功能了。")


if __name__ == '__main__':
    main()