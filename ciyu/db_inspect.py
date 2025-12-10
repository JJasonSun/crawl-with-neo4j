# -*- coding: utf-8 -*-
"""
数据库检查与打印工具（针对 ciyu）

功能：
 - 导入 `ciyu_mysql` 中的 `get_database_connection` 与 `mysql_config`
 - 打印样例行、索引信息与表结构描述（针对 `hanyuguoxue_ciyu` 与 `ciyu_relation`）

用法：
    python db_inspect.py
"""

from datetime import datetime
from typing import Optional

from ciyu_mysql import get_database_connection, mysql_config


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _print_title(title: str):
    print('\n' + '=' * 60)
    print(f'{title}  [{_now()}]')
    print('-' * 60)


def print_samples(conn=None, limit_main=50, limit_rel=20):
    """打印基础表与关系表的样例行。"""
    close_conn = False
    if conn is None:
        conn = get_database_connection()
        close_conn = True

    if not conn:
        print('[WARN] 无法建立数据库连接，跳过样例打印')
        return

    try:
        cur = conn.cursor()
        _print_title('汉语国学词语表（样例）')
        cur.execute('SELECT id, word, pinyin, part_of_speech, definition, is_common, synonyms, antonyms FROM hanyuguoxue_ciyu ORDER BY id DESC LIMIT %s', (limit_main,))
        rows = cur.fetchall()
        
        # 使用制表符分隔的格式，更清晰易读
        print("ID\t词语\t拼音\t词性\t定义\t常用\t同义词\t反义词")
        print("-" * 100)
        
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
            word = (r['word'] or 'None')
            pinyin = (r['pinyin'] or 'None')
            part_of_speech = (r['part_of_speech'] or 'None')
            definition = (r['definition'] or 'None')
            is_common = '是' if r['is_common'] else '否'
            # 截断定义字段，保持表格整齐
            if len(definition) > 30:
                definition = definition[:30] + '...'
            synonyms = synonyms[:20] + ('...' if len(synonyms) > 20 else '')
            antonyms = antonyms[:20] + ('...' if len(antonyms) > 20 else '')
            
            print(f"{r['id']}\t{word}\t{pinyin}\t{part_of_speech}\t{definition}\t{is_common}\t{synonyms}\t{antonyms}")

        _print_title('词语关系表（样例）')
        cur.execute('SELECT r.id, r.min_id, r.max_id, r.relation_type, w1.word as word1, w2.word as word2 FROM ciyu_relation r LEFT JOIN hanyuguoxue_ciyu w1 ON r.min_id = w1.id LEFT JOIN hanyuguoxue_ciyu w2 ON r.max_id = w2.id ORDER BY r.id DESC LIMIT %s', (limit_rel,))
        rows = cur.fetchall()
        
        # 使用制表符分隔的格式
        print("ID\t最小ID\t最大ID\t关系类型\t词语1\t词语2")
        print("-" * 60)
        
        for r in rows:
            relation_type = '同义' if r['relation_type'] == 'synonym' else '反义'
            word1 = r['word1'] or f"ID:{r['min_id']}"
            word2 = r['word2'] or f"ID:{r['max_id']}"
            
            print(f"{r['id']}\t{r['min_id']}\t{r['max_id']}\t{relation_type}\t{word1}\t{word2}")

    finally:
        if close_conn and conn:
            conn.close()


def list_table_indexes(table: Optional[str] = None, conn=None):
    """列出表索引（默认列出两张表）。"""
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
        tables = [table] if table else ['hanyuguoxue_ciyu', 'ciyu_relation']

        for t in tables:
            table_name = '汉语国学词语表' if t == 'hanyuguoxue_ciyu' else '词语关系表'
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
        
        display_name = '汉语国学词语表' if table_name == 'hanyuguoxue_ciyu' else '词语关系表'
        _print_title(f'{display_name}的结构描述')
        for r in rows:
            print(f"  - {r['COLUMN_NAME']} | {r['COLUMN_TYPE']} | nullable={r['IS_NULLABLE']} | default={r['COLUMN_DEFAULT']}")

    finally:
        if close_conn and conn:
            conn.close()


def print_all_inspect():
    print_samples()
    list_table_indexes()
    describe_table('hanyuguoxue_ciyu')
    describe_table('ciyu_relation')


if __name__ == '__main__':
    print_all_inspect()
