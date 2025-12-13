# -*- coding: utf-8 -*-
"""通用的清表脚本：`clear_crawled_data.py`

支持交互式选择要清空的数据库类型（chengyu 或 ciyu）。
运行时会提示用户输入选择，需要两次确认才会执行。

用法：
    python clear_crawled_data.py

注意：TRUNCATE 会永久删除表内数据，请谨慎使用。
"""
from typing import List
import importlib

# 脚本支持删除的两张表：
#  - chengyu -> ['chengyu_relation', 'hanyuguoxue_chengyu']
#  - ciyu   -> ['ciyu_relation', 'hanyuguoxue_ciyu']
# 为了确保能清空父表，脚本**会始终禁用外键检查**。
# 运行时会提示输入 'chengyu' 或 'ciyu' 来确认删除哪个表
# =======================================================================
TARGET_SOURCE = None  # 默认无值，运行时通过用户输入确定


def _get_connection_for(source: str):
    """动态导入对应模块并返回 get_database_connection() 的结果。"""
    if source == 'chengyu':
        mod = importlib.import_module('chengyu.chengyu_DB')
        return getattr(mod, 'get_database_connection')()
    if source == 'ciyu':
        mod = importlib.import_module('ciyu.ciyu_DB')
        return getattr(mod, 'get_database_connection')()
    raise ValueError('未知的数据源: ' + source)


def clear_tables(tables: List[str], source: str = 'chengyu', interactive: bool = True) -> int:
    """清空指定 source 下的 tables。

    返回退出码：0 成功，非 0 失败/取消。
    """
    if interactive:
        print('\n' + '*' * 80)
        print('请选择要清空的数据库类型：')
        print('  输入 chengyu - 清空成语数据库')
        print('  输入 ciyu   - 清空词语数据库')
        print('按 Ctrl+C 取消操作')
        print("请输入选择：", end='')
        try:
            user_choice = input().strip()
        except KeyboardInterrupt:
            print('\n操作已取消')
            return 0
        except Exception:
            print('\n未收到输入，已取消操作')
            return 4
        
        if user_choice not in ['chengyu', 'ciyu']:
            print('输入无效，已取消操作。')
            return 5
        
        # 更新source和tables为用户选择
        source = user_choice
        tables = _default_tables_for(source)
        
        print(f'\n确认：即将永久删除 {source} 数据库中的表: {tables}')
        print("再次输入 '{source}' 确认删除：", end='')
        try:
            confirm = input().strip()
        except KeyboardInterrupt:
            print('\n操作已取消')
            return 0
        except Exception:
            print('\n未收到输入，已取消操作')
            return 4
        
        if confirm != source:
            print('确认失败，已取消操作。')
            return 5
            
        print('*' * 80 + '\n')

    # 进入真正的执行逻辑（用户已确认）

    conn = _get_connection_for(source)
    if not conn:
        print('无法连接到数据库，退出')
        return 2
    cur = conn.cursor()
    try:
        # 始终临时禁用外键检查以确保可以 TRUNCATE 父表
        cur.execute('SET FOREIGN_KEY_CHECKS=0')
        for t in tables:
            print('清理表:', t)
            cur.execute(f'TRUNCATE TABLE {t}')
        # 恢复外键检查
        cur.execute('SET FOREIGN_KEY_CHECKS=1')
        conn.commit()
        print('清理完成')
        return 0
    except Exception as e:
        print('清理失败:', e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 3
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _default_tables_for(source: str) -> List[str]:
    if source == 'chengyu':
        return ['chengyu_relation', 'hanyuguoxue_chengyu']
    if source == 'ciyu':
        return ['ciyu_relation', 'hanyuguoxue_ciyu']
    raise ValueError('未知的数据源: ' + source)


if __name__ == '__main__':
    # 如果TARGET_SOURCE有值，使用该值；否则让用户选择
    if TARGET_SOURCE:
        tables = _default_tables_for(TARGET_SOURCE)
        exit(clear_tables(tables, source=TARGET_SOURCE, interactive=True))
    else:
        # 交互式选择
        exit(clear_tables([], source='', interactive=True))
