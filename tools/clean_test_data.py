#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理测试数据工具

删除测试过程中意外插入到数据库的测试数据。
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import MYSQL_CONFIG


def get_database_connection():
    """获取 MySQL 数据库连接"""
    try:
        import pymysql
        cfg = MYSQL_CONFIG.copy()
        cfg.update({"charset": "utf8mb4"})
        return pymysql.connect(**cfg)
    except Exception as e:
        print(f"无法建立数据库连接: {e}")
        return None


def clean_test_data():
    """清理测试数据"""
    conn = get_database_connection()
    if not conn:
        print("无法连接数据库")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 查找测试URL的记录
        print("正在查找测试数据...")
        
        # 查找成语测试数据
        cursor.execute("""
            SELECT id, chengyu FROM hanyuguoxue_chengyu 
            WHERE url LIKE '%test.com%'
        """)
        chengyu_test_records = cursor.fetchall()
        
        # 查找词语测试数据
        cursor.execute("""
            SELECT id, word FROM hanyuguoxue_ciyu 
            WHERE url LIKE '%test.com%'
        """)
        ciyu_test_records = cursor.fetchall()
        
        # 额外查找可能被测试插入的空字段记录
        cursor.execute("""
            SELECT id, chengyu FROM hanyuguoxue_chengyu 
            WHERE chengyu IN ('顺风顺水') AND (pinyin IS NULL OR explanation IS NULL)
        """)
        empty_chengyu_records = cursor.fetchall()
        
        if not chengyu_test_records and not ciyu_test_records and not empty_chengyu_records:
            print("✓ 没有找到测试数据")
            return True
        
        print(f"找到 {len(chengyu_test_records)} 条成语测试记录（URL匹配）")
        print(f"找到 {len(ciyu_test_records)} 条词语测试记录（URL匹配）")
        print(f"找到 {len(empty_chengyu_records)} 条空字段成语记录（可能是测试数据）")
        
        # 显示将要删除的数据
        all_chengyu_to_delete = chengyu_test_records + empty_chengyu_records
        if all_chengyu_to_delete:
            print("\n将要删除的成语测试记录:")
            for record in all_chengyu_to_delete:
                print(f"  ID: {record[0]}, 成语: {record[1]}")
        
        if ciyu_test_records:
            print("\n将要删除的词语测试记录:")
            for record in ciyu_test_records:
                print(f"  ID: {record[0]}, 词语: {record[1]}")
        
        # 确认删除
        confirm = input("\n确认删除这些测试数据吗？(输入 'yes' 确认): ")
        if confirm.lower() != 'yes':
            print("取消删除操作")
            return False
        
        # 开始删除
        print("\n开始删除测试数据...")
        
        # 删除成语关系（先删除关系，再删除主记录）
        if all_chengyu_to_delete:
            chengyu_ids = [record[0] for record in all_chengyu_to_delete]
            placeholders = ','.join(['%s'] * len(chengyu_ids))
            
            # 先删除与这些成语相关的所有关系
            cursor.execute(f"""
                DELETE FROM chengyu_relation 
                WHERE min_id IN ({placeholders}) OR max_id IN ({placeholders})
            """, chengyu_ids + chengyu_ids)
            
            deleted_relations = cursor.rowcount
            print(f"删除了 {deleted_relations} 条成语关系记录")
            
            # 删除成语记录
            cursor.execute(f"""
                DELETE FROM hanyuguoxue_chengyu 
                WHERE id IN ({placeholders})
            """, chengyu_ids)
            
            deleted_chengyu = cursor.rowcount
            print(f"删除了 {deleted_chengyu} 条成语记录")
        
        # 删除词语关系
        if ciyu_test_records:
            ciyu_ids = [record[0] for record in ciyu_test_records]
            placeholders = ','.join(['%s'] * len(ciyu_ids))
            
            cursor.execute(f"""
                DELETE FROM ciyu_relation 
                WHERE min_id IN ({placeholders}) OR max_id IN ({placeholders})
            """, ciyu_ids + ciyu_ids)
            
            deleted_ciyu_relations = cursor.rowcount
            print(f"删除了 {deleted_ciyu_relations} 条词语关系记录")
            
            cursor.execute(f"""
                DELETE FROM hanyuguoxue_ciyu 
                WHERE id IN ({placeholders})
            """, ciyu_ids)
            
            deleted_ciyu = cursor.rowcount
            print(f"删除了 {deleted_ciyu} 条词语记录")
        
        # 提交事务
        conn.commit()
        print("\n✓ 测试数据清理完成")
        return True
        
    except Exception as e:
        print(f"清理测试数据时出错: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def main():
    """主函数"""
    print("测试数据清理工具")
    print("=" * 50)
    
    success = clean_test_data()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())