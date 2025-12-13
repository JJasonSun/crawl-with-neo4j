# -*- coding: utf-8 -*-
"""
通用数据库检查与打印工具（支持成语和词语）

功能：
 - 统一支持成语和词语数据库的检查
 - 统一打印格式（标题分隔线、键值对整齐对齐）
 - 提供三个主要函数：print_samples(), list_table_indexes(), describe_tables()
 - 支持命令行参数选择检查类型

用法：
    python tools/db_inspect.py chengyu  # 检查成语数据库
    python tools/db_inspect.py ciyu     # 检查词语数据库
    python tools/db_inspect.py          # 默认检查成语数据库
"""

from datetime import datetime
from typing import Optional
import sys
import os
import pymysql

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from common.config import MYSQL_CONFIG


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _print_title(title: str):
    print('\n' + '=' * 60)
    print(f'{title}  [{_now()}]')
    print('-' * 60)


def get_database_connection():
    """获取 MySQL 数据库连接"""
    try:
        cfg = MYSQL_CONFIG.copy()
        cfg.update({"charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor})
        conn = pymysql.connect(**cfg)
        # 测试基本权限
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return conn
    except Exception as e:
        print(f"无法建立数据库连接: {e}")
        return None


def get_table_config(db_type: str):
    """获取数据库类型对应的配置"""
    if db_type == 'chengyu':
        return {
            'main_table': 'hanyuguoxue_chengyu',
            'relation_table': 'chengyu_relation',
            'main_display_name': '汉语国学成语表',
            'relation_display_name': '成语关系表',
            'main_fields': 'id, chengyu, pinyin, emotion, explanation, synonyms, antonyms',
            'relation_fields': 'r.id, r.min_id, r.max_id, r.relation_type, c1.chengyu as chengyu1, c2.chengyu as chengyu2',
            'relation_joins': 'LEFT JOIN hanyuguoxue_chengyu c1 ON r.min_id = c1.id LEFT JOIN hanyuguoxue_chengyu c2 ON r.max_id = c2.id',
            'headers': ['ID', '成语', '拼音', '情感', '解释', '同义词', '反义词'],
            'relation_headers': ['ID', '最小ID', '最大ID', '关系类型', '词1', '词2']
        }
    elif db_type == 'ciyu':
        return {
            'main_table': 'hanyuguoxue_ciyu',
            'relation_table': 'ciyu_relation',
            'main_display_name': '汉语国学词语表',
            'relation_display_name': '词语关系表',
            'main_fields': 'id, word, pinyin, part_of_speech, definition, is_common, synonyms, antonyms',
            'relation_fields': 'r.id, r.min_id, r.max_id, r.relation_type, w1.word as word1, w2.word as word2',
            'relation_joins': 'LEFT JOIN hanyuguoxue_ciyu w1 ON r.min_id = w1.id LEFT JOIN hanyuguoxue_ciyu w2 ON r.max_id = w2.id',
            'headers': ['ID', '词语', '拼音', '词性', '定义', '常用', '同义词', '反义词'],
            'relation_headers': ['ID', '最小ID', '最大ID', '关系类型', '词1', '词2']
        }
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")


def print_samples(db_type: str = 'chengyu', conn=None, limit_main=10, limit_rel=20):
    """打印基础表与关系表的样例行"""
    config = get_table_config(db_type)
    
    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    if not conn:
        print('[WARN] 无法建立数据库连接，跳过样例打印')
        return

    try:
        cur = conn.cursor()
        
        # 显示数据总数
        _print_title(f'{config["main_display_name"]}（数据统计）')
        count_query = f'SELECT COUNT(*) as total_count FROM {config["main_table"]}'
        cur.execute(count_query)
        count_result = cur.fetchone()
        total_count = count_result['total_count']
        print(f'总记录数: {total_count:,}')
        
        # 显示关系表总数
        rel_count_query = f'SELECT COUNT(*) as total_count FROM {config["relation_table"]}'
        cur.execute(rel_count_query)
        rel_count_result = cur.fetchone()
        total_rel_count = rel_count_result['total_count']
        print(f'总关系数: {total_rel_count:,}')
        
        _print_title(f'{config["main_display_name"]}（样例）')
        query = f'SELECT {config["main_fields"]} FROM {config["main_table"]} ORDER BY id DESC LIMIT %s'
        cur.execute(query, (limit_main,))
        rows = cur.fetchall()
        
        # 打印表头
        print('\t'.join(config["headers"]))
        print("-" * 100)
        
        for r in rows:
            # 处理每一行的数据
            row_data = []
            for field in config["main_fields"].split(', '):
                value = r[field]  # 使用字段名而不是索引
                if value is None:
                    row_data.append('NULL')
                elif isinstance(value, str) and len(value) > 20:
                    row_data.append(value[:17] + '...')
                else:
                    row_data.append(str(value))
            print('\t'.join(row_data))
        
        # 关系表样例
        _print_title(f'{config["relation_display_name"]}（样例）')
        cur.execute(f'SELECT {config["relation_fields"]} FROM {config["relation_table"]} r {config["relation_joins"]} ORDER BY r.id DESC LIMIT %s', (limit_rel,))
        rows = cur.fetchall()
        
        relation_headers = config.get('relation_headers', ['ID', '最小ID', '最大ID', '关系类型', '词1', '词2'])
        print('\t'.join(relation_headers))
        print("-" * 100)
        
        for r in rows:
            row_data = []
            # 根据数据库类型使用不同的字段名
            if db_type == 'chengyu':
                fields = ['id', 'min_id', 'max_id', 'relation_type', 'chengyu1', 'chengyu2']
            else:  # ciyu
                fields = ['id', 'min_id', 'max_id', 'relation_type', 'word1', 'word2']
            
            for field in fields:
                value = r.get(field, 'NULL')
                if value is None:
                    row_data.append('NULL')
                elif isinstance(value, str) and len(value) > 20:
                    row_data.append(value[:17] + '...')
                else:
                    row_data.append(str(value))
            print('\t'.join(row_data))
            
    except Exception as e:
        print(f'[ERROR] 打印样例失败: {e}')
    finally:
        if close_conn and conn:
            conn.close()


def list_table_indexes(db_type: str = 'chengyu', conn=None):
    """列出指定表的索引信息"""
    config = get_table_config(db_type)
    
    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    if not conn:
        print('[WARN] 无法建立数据库连接，跳过索引打印')
        return

    try:
        cur = conn.cursor()
        tables = [config["main_table"], config["relation_table"]]
        
        for table in tables:
            display_name = config["main_display_name"] if table == config["main_table"] else config["relation_display_name"]
            _print_title(f'{display_name} - 索引信息')
            
            try:
                # 先检查表是否存在
                cur.execute(f"SHOW TABLES LIKE '{table}'")
                if not cur.fetchone():
                    print(f'  表 {table} 不存在')
                    continue
                
                # 对于SHOW INDEX和DESCRIBE，使用普通cursor
                normal_cursor = conn.cursor(cursor=pymysql.cursors.Cursor)
                normal_cursor.execute(f'SHOW INDEX FROM {table}')
                indexes = normal_cursor.fetchall()
                normal_cursor.close()
                
                if not indexes:
                    print('  无索引')
                    continue
                    
                # 按索引名分组
                index_groups = {}
                for idx in indexes:
                    key_name = idx[2]
                    if key_name not in index_groups:
                        index_groups[key_name] = []
                    index_groups[key_name].append(idx)
                
                for key_name, idx_list in index_groups.items():
                    is_unique = 'UNIQUE' if idx_list[0][1] == 0 else 'NON-UNIQUE'
                    print(f'  {key_name} ({is_unique})')
                    for idx in idx_list:
                        print(f'    - Column: {idx[4]}, Collation: {idx[5]}, Cardinality: {idx[6]}')
            except Exception as e:
                print(f'  [ERROR] 获取 {table} 索引失败: {e}')
                    
    except Exception as e:
        print(f'[ERROR] 列出索引失败: {e}')
    finally:
        if close_conn and conn:
            conn.close()


def describe_table(db_type: str = 'chengyu', table: Optional[str] = None):
    """描述表结构"""
    config = get_table_config(db_type)
    
    close_conn = False
    conn = get_database_connection()
    if not conn:
        print('[WARN] 无法建立数据库连接，跳过表结构描述')
        return

    try:
        cur = conn.cursor()
        tables = [table] if table else [config["main_table"], config["relation_table"]]
        
        for table_name in tables:
            display_name = config["main_display_name"] if table_name == config["main_table"] else config["relation_display_name"]
            _print_title(f'{display_name} - 表结构')
            
            try:
                # 先检查表是否存在
                cur.execute(f"SHOW TABLES LIKE '{table_name}'")
                if not cur.fetchone():
                    print(f'  表 {table_name} 不存在')
                    continue
                
                # 对于SHOW INDEX和DESCRIBE，使用普通cursor
                normal_cursor = conn.cursor(cursor=pymysql.cursors.Cursor)
                normal_cursor.execute(f'DESCRIBE {table_name}')
                columns = normal_cursor.fetchall()
                normal_cursor.close()
                
                if not columns:
                    print('  表不存在或无权限访问')
                    continue
                    
                # 格式化输出
                print(f'{"字段名":<20} {"类型":<20} {"允许NULL":<10} {"键":<10} {"默认值":<15} {"额外信息"}')
                print("-" * 100)
                
                for col in columns:
                    field = col[0] or ''
                    type_info = col[1] or ''
                    null_allowed = col[2] or ''
                    key = col[3] or ''
                    default = str(col[4]) if col[4] is not None else 'NULL'
                    extra = col[5] or ''
                    
                    print(f'{field:<20} {type_info:<20} {null_allowed:<10} {key:<10} {default:<15} {extra}')
            except Exception as e:
                print(f'  [ERROR] 获取 {table_name} 表结构失败: {e}')
                
    except Exception as e:
        print(f'[ERROR] 描述表结构失败: {e}')
    finally:
        if close_conn and conn:
            conn.close()


def print_all_inspect(db_type: str = 'chengyu'):
    """按顺序打印样例、索引和表结构"""
    print_samples(db_type)
    list_table_indexes(db_type)
    describe_table(db_type)


if __name__ == '__main__':
    # 支持命令行参数
    db_type = sys.argv[1] if len(sys.argv) > 1 else 'chengyu'
    if db_type not in ['chengyu', 'ciyu']:
        print("用法: python db_inspect.py [chengyu|ciyu]")
        sys.exit(1)
    
    print_all_inspect(db_type)