# -*- coding: utf-8 -*-
"""
数据库检查与打印工具（合并并替代旧的 query_tables / list_indexes / describe_tables）。

功能：
 - 统一导入数据库辅助模块（相对导入），若导入失败则在运行时优雅提示。
 - 统一打印格式（标题分隔线、键值对整齐对齐）。
 - 提供三个主要函数：print_samples(), list_table_indexes(), describe_tables()
 - 直接运行时会按顺序打印样例、索引与表结构描述。

用法：
    python db_inspect.py
"""

from datetime import datetime
from typing import Optional

from hanyuguoxue_chengyu import get_database_connection, mysql_config


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _print_title(title: str):
    print('\n' + '=' * 60)
    print(f'{title}  [{_now()}]')
    print('-' * 60)



def print_samples(conn=None, limit_main=10, limit_rel=20):
    """打印基础表与关系表的样例行。

    如果未传入 conn，将尝试建立连接；失败时会打印提示并返回。
    """
    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    if not conn:
        print('[WARN] 无法建立数据库连接，跳过样例打印')
        return

    try:
        cur = conn.cursor()
        _print_title('汉语国学成语表（样例）')
        cur.execute('SELECT id, chengyu, pinyin, synonyms, antonyms FROM hanyuguoxue_chengyu ORDER BY id DESC LIMIT %s', (limit_main,))
        rows = cur.fetchall()
        for r in rows:
            print(r)

        _print_title('成语关系表（样例）')
        cur.execute('SELECT id, min_id, max_id, relation_type FROM chengyu_relation ORDER BY id DESC LIMIT %s', (limit_rel,))
        for r in cur.fetchall():
            print(r)

    finally:
        if close_conn and conn:
            conn.close()


def list_table_indexes(table: Optional[str] = None, conn=None):
    """列出表索引（默认列出两张表）。

    若未传入 conn，会尝试建立连接；失败时会打印提示并返回。
    """
    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    if not conn:
        print('[WARN] 无法建立数据库连接，跳过索引查询')
        return

    try:
        cur = conn.cursor()
        schema = mysql_config.get('database')
        tables = [table] if table else ['hanyuguoxue_chengyu', 'chengyu_relation']

        for t in tables:
            table_name = '汉语国学成语表' if t == 'hanyuguoxue_chengyu' else '成语关系表'
            _print_title(f'{table_name}的索引信息')
            cur.execute(
                "SELECT INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY INDEX_NAME, SEQ_IN_INDEX",
                (schema, t)
            )
            rows = cur.fetchall()
            if not rows:
                print(f'  {table_name}: 无索引信息或表不存在')
                continue
            idx = {}
            for r in rows:
                name = r['INDEX_NAME']
                idx.setdefault(name, []).append(r['COLUMN_NAME'])
            for name, cols in idx.items():
                print(f'  - {name}: {cols}')

    finally:
        if close_conn and conn:
            conn.close()


def describe_table(table_name: str, conn=None):
    """打印单表的列描述（name,type,nullable,default）。"""
    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    if not conn:
        print(f'[WARN] 无法建立数据库连接，跳过 {table_name} 的描述')
        return

    try:
        cur = conn.cursor()
        schema = mysql_config.get('database')
        cur.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
            "ORDER BY ORDINAL_POSITION",
            (schema, table_name)
        )
        rows = cur.fetchall()
        if not rows:
            print(f'  {table_name}: 无列信息或表不存在')
            return
        
        # 将表名转换为中文显示
        display_name = '汉语国学成语表' if table_name == 'hanyuguoxue_chengyu' else '成语关系表'
        _print_title(f'{display_name}的结构描述')
        for r in rows:
            print(f"  - {r['COLUMN_NAME']} | {r['COLUMN_TYPE']} | nullable={r['IS_NULLABLE']} | default={r['COLUMN_DEFAULT']}")

    finally:
        if close_conn and conn:
            conn.close()


def print_all_inspect():
    """按顺序打印样例、索引和表结构（默认目标表）。"""
    print_samples()
    list_table_indexes()
    describe_table('hanyuguoxue_chengyu')
    describe_table('chengyu_relation')


if __name__ == '__main__':
    print_all_inspect()
