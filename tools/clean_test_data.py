#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理测试数据工具

删除测试过程中意外插入到数据库的测试数据。
支持清理按名称识别的测试数据。
"""

import sys
import os
import pymysql

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import MYSQL_CONFIG


def get_database_connection():
    """获取 MySQL 数据库连接"""
    try:
        cfg = MYSQL_CONFIG.copy()
        cfg.update({"charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor})
        return pymysql.connect(**cfg)
    except Exception as e:
        print(f"无法建立数据库连接: {e}")
        return None


def check_test_data():
    """检查测试数据"""
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # 查找测试数据
        print("正在查找测试数据...")
        print("="*60)
        
        # 查找成语测试数据
        cursor.execute("""
            SELECT id, chengyu, pinyin, explanation FROM hanyuguoxue_chengyu 
            WHERE chengyu LIKE '%测试%' OR chengyu LIKE '%老师测试%'
            ORDER BY id DESC
        """)
        chengyu_test_records = cursor.fetchall()
        
        print(f"\n成语测试数据: {len(chengyu_test_records)} 条")
        if chengyu_test_records:
            print(f"{'ID':<10} {'成语':<20} {'拼音':<20} {'解释':<50}")
            print("-" * 100)
            for record in chengyu_test_records[:10]:  # 只显示前10条
                id_val = record['id']
                chengyu = record['chengyu'][:18] + '...' if len(record['chengyu']) > 18 else record['chengyu']
                pinyin = record['pinyin'][:18] + '...' if record['pinyin'] and len(record['pinyin']) > 18 else (record['pinyin'] or '')
                explanation = (record['explanation'] or '')[:48] + '...' if record['explanation'] and len(record['explanation']) > 48 else (record['explanation'] or '')
                print(f"{id_val:<10} {chengyu:<20} {pinyin:<20} {explanation:<50}")
        
        # 查找词语测试数据
        cursor.execute("""
            SELECT id, word, pinyin, definition FROM hanyuguoxue_ciyu 
            WHERE word LIKE '%测试%'
            ORDER BY id DESC
        """)
        ciyu_test_records = cursor.fetchall()
        
        print(f"\n词语测试数据: {len(ciyu_test_records)} 条")
        if ciyu_test_records:
            print(f"{'ID':<10} {'词语':<20} {'拼音':<20} {'定义':<50}")
            print("-" * 100)
            for record in ciyu_test_records[:10]:  # 只显示前10条
                id_val = record['id']
                word = record['word'][:18] + '...' if len(record['word']) > 18 else record['word']
                pinyin = record['pinyin'][:18] + '...' if record['pinyin'] and len(record['pinyin']) > 18 else (record['pinyin'] or '')
                definition = (record['definition'] or '')[:48] + '...' if record['definition'] and len(record['definition']) > 48 else (record['definition'] or '')
                print(f"{id_val:<10} {word:<20} {pinyin:<20} {definition:<50}")
        
                # 注意：不删除关系表中的测试数据，因为没有测试插入关系
        
        if not chengyu_test_records and not ciyu_test_records:
            print("✓ 没有找到测试数据")
            return True
        
        # 确认删除
        print(f"\n将删除 {len(chengyu_test_records)} 条成语测试记录")
        print(f"将删除 {len(ciyu_test_records)} 条词语测试记录")
        print("注意：不删除关系表数据")
        
        confirm = input("\n确认删除这些测试数据吗？(输入 'yes' 确认): ")
        if confirm.lower() != 'yes':
            print("取消删除操作")
            return False
        
        # 开始删除
        print("\n开始删除测试数据...")
        
        # 删除成语记录（不删除关系表）
        if chengyu_test_records:
            cursor.execute("""
                DELETE FROM hanyuguoxue_chengyu 
                WHERE chengyu LIKE '%测试%' OR chengyu LIKE '%老师测试%'
            """)
            
            deleted_chengyu = cursor.rowcount
            print(f"删除了 {deleted_chengyu} 条成语记录")
        
        # 删除词语记录（不删除关系表）
        if ciyu_test_records:
            cursor.execute("""
                DELETE FROM hanyuguoxue_ciyu 
                WHERE word LIKE '%测试%'
            """)
            
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


def clean_test_data():
    """主函数 - 清理测试数据"""
    return check_test_data()


if __name__ == '__main__':
    clean_test_data()


def main():
    """主函数"""
    print("测试数据清理工具")
    print("=" * 50)
    
    success = clean_test_data()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())