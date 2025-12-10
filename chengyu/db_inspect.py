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

from chengyu_mysql import get_database_connection, mysql_config


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
        cur.execute('SELECT id, chengyu, pinyin, emotion, explanation, synonyms, antonyms FROM hanyuguoxue_chengyu ORDER BY id DESC LIMIT %s', (limit_main,))
        rows = cur.fetchall()
        
        # 使用制表符分隔的格式，更清晰易读
        print("ID\t成语\t拼音\t感情色彩\t释义\t同义词\t反义词")
        print("-" * 90)
        
        for r in rows:
            # 处理JSON字段，使其更易读
            synonyms = r['synonyms'] if r['synonyms'] else 'None'
            antonyms = r['antonyms'] if r['antonyms'] else 'None'
            
            # 如果是JSON字符串，尝试解析并截断显示
            if synonyms and synonyms.startswith('['):
                try:
                    import json
                    syn_list = json.loads(synonyms)
                    synonyms = ', '.join(syn_list[:3])  # 只显示前3个
                    if len(syn_list) > 3:
                        synonyms += '...'
                except:
                    pass
                    
            if antonyms and antonyms.startswith('['):
                try:
                    import json
                    ant_list = json.loads(antonyms)
                    antonyms = ', '.join(ant_list[:3])  # 只显示前3个
                    if len(ant_list) > 3:
                        antonyms += '...'
                except:
                    pass
            
            # 限制字段长度以避免输出过长
            chengyu = (r['chengyu'] or 'None')
            pinyin = (r['pinyin'] or 'None')
            emotion = (r['emotion'] or 'None')
            explanation = (r['explanation'] or 'None')
            # 截断释义字段，保持表格整齐
            if len(explanation) > 30:
                explanation = explanation[:30] + '...'
            synonyms = synonyms[:20] + ('...' if len(synonyms) > 20 else '')
            antonyms = antonyms[:20] + ('...' if len(antonyms) > 20 else '')
            
            print(f"{r['id']}\t{chengyu}\t{pinyin}\t{emotion}\t{explanation}\t{synonyms}\t{antonyms}")

        _print_title('成语关系表（样例）')
        cur.execute('SELECT r.id, r.min_id, r.max_id, r.relation_type, c1.chengyu as chengyu1, c2.chengyu as chengyu2 FROM chengyu_relation r LEFT JOIN hanyuguoxue_chengyu c1 ON r.min_id = c1.id LEFT JOIN hanyuguoxue_chengyu c2 ON r.max_id = c2.id ORDER BY r.id DESC LIMIT %s', (limit_rel,))
        rows = cur.fetchall()
        
        # 使用制表符分隔的格式
        print("ID\t最小ID\t最大ID\t关系类型\t成语1\t成语2")
        print("-" * 60)
        
        for r in rows:
            relation_type = '同义' if r['relation_type'] == 'synonym' else '反义'
            chengyu1 = r['chengyu1'] or f"ID:{r['min_id']}"
            chengyu2 = r['chengyu2'] or f"ID:{r['max_id']}"
            
            print(f"{r['id']}\t{r['min_id']}\t{r['max_id']}\t{relation_type}\t{chengyu1}\t{chengyu2}")

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
