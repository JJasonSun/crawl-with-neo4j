#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用词语/成语检查工具

根据输入字数自动判断：
- 2个字：查词语
- 其他：查成语

用法：
    python tools/check_word.py 爱亲     # 查词语
    python tools/check_word.py 一帆风顺 # 查成语
    python tools/check_word.py          # 交互式输入
"""

import sys
import os
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import MYSQL_CONFIG


def get_database_connection():
    """获取 MySQL 数据库连接"""
    try:
        import pymysql
        cfg = MYSQL_CONFIG.copy()
        cfg.update({"charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor})
        return pymysql.connect(**cfg)
    except Exception as e:
        print(f"无法建立数据库连接: {e}")
        return None


def check_chengyu(conn, word: str) -> bool:
    """检查成语是否存在"""
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM hanyuguoxue_chengyu WHERE chengyu=%s', (word,))
        rows = cur.fetchall()
        
        if rows:
            print(f"✓ 成语 '{word}' 存在于数据库中 (共 {len(rows)} 条记录):")
            for i, row in enumerate(rows, 1):
                print(f"  记录 {i}:")
                print(f"    ID: {row['id']}")
                print(f"    成语: {row['chengyu']}")
                print(f"    拼音: {row['pinyin']}")
                print(f"    注音: {row['zhuyin']}")
                print(f"    情感: {row['emotion']}")
                print(f"    解释: {row['explanation']}")
                print(f"    来源: {row['source']}")
                print(f"    用法: {row['usage']}")
                print(f"    例句: {row['example']}")
                print(f"    同义词: {row['synonyms']}")
                print(f"    反义词: {row['antonyms']}")
                print(f"    翻译: {row['translation']}")
                print(f"    错误信息: {row['error']}")
                print(f"    创建时间: {row['created_at']}")
                print(f"    更新时间: {row['updated_at']}")
                print()
            return True
        else:
            print(f"✗ 成语 '{word}' 不存在于数据库中")
            return False
    except Exception as e:
        print(f"查询成语时出错: {e}")
        return False


def check_ciyu(conn, word: str) -> bool:
    """检查词语是否存在"""
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM hanyuguoxue_ciyu WHERE word=%s', (word,))
        rows = cur.fetchall()
        
        if rows:
            print(f"✓ 词语 '{word}' 存在于数据库中 (共 {len(rows)} 条记录):")
            for i, row in enumerate(rows, 1):
                print(f"  记录 {i}:")
                print(f"    ID: {row['id']}")
                print(f"    词语: {row['word']}")
                print(f"    拼音: {row['pinyin']}")
                print(f"    注音: {row['zhuyin']}")
                print(f"    词性: {row['part_of_speech']}")
                print(f"    常用: {'是' if row['is_common'] else '否'}")
                print(f"    定义: {row['definition']}")
                print(f"    同义词: {row['synonyms']}")
                print(f"    反义词: {row['antonyms']}")
                print(f"    错误信息: {row['error']}")
                print(f"    创建时间: {row['created_at']}")
                print(f"    更新时间: {row['updated_at']}")
                print()
            return True
        else:
            print(f"✗ 词语 '{word}' 不存在于数据库中")
            return False
    except Exception as e:
        print(f"查询词语时出错: {e}")
        return False


def check_word(word: str, force_type: Optional[str] = None) -> bool:
    """
    检查词语/成语
    
    Args:
        word: 要检查的词语
        force_type: 强制指定类型 ('chengyu' 或 'ciyu')，None 表示自动判断
    
    Returns:
        bool: 是否找到记录
    """
    if not word or not word.strip():
        print("请输入有效的词语")
        return False
    
    word = word.strip()
    conn = get_database_connection()
    if not conn:
        print("无法连接数据库")
        return False
    
    try:
        found = False
        
        # 根据字数或强制类型决定查询方式
        if force_type == 'chengyu':
            found = check_chengyu(conn, word)
        elif force_type == 'ciyu':
            found = check_ciyu(conn, word)
        else:
            # 自动判断：只有2个字查词语，其他都查成语
            if len(word) == 2:
                print(f"检测到2个字，查询词语...")
                found = check_ciyu(conn, word)
            else:
                print(f"检测到{len(word)}个字，查询成语...")
                found = check_chengyu(conn, word)
        
        return found
    finally:
        conn.close()


def interactive_mode():
    """交互式模式"""
    print("词语/成语检查工具 (输入 'quit' 或 'exit' 退出)")
    print("=" * 50)
    
    while True:
        try:
            word = input("请输入要查询的词语: ").strip()
            if not word:
                continue
            if word.lower() in ('quit', 'exit', 'q'):
                print("再见!")
                break
            
            print()
            check_word(word)
            print("=" * 50)
            
        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except Exception as e:
            print(f"输入错误: {e}")


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 命令行模式
        word = sys.argv[1]
        force_type = None
        
        if len(sys.argv) > 2:
            force_type = sys.argv[2].lower()
            if force_type not in ('chengyu', 'ciyu'):
                print("强制类型必须是 'chengyu' 或 'ciyu'")
                return 1
        
        found = check_word(word, force_type)
        return 0 if found else 1
    else:
        # 交互式模式
        interactive_mode()
        return 0


if __name__ == '__main__':
    sys.exit(main())