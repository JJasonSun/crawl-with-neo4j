# -*- coding: utf-8 -*-
"""通用的清表脚本：`clear_crawled_data.py`

将可在文件顶部修改 `TARGET_TABLES` 与 `USE_FOREIGN_KEY_CHECKS` 来控制哪些表会被清空。
支持交互确认，默认会要求输入 YES 才会执行。

用法：
    python clear_crawled_data.py

注意：TRUNCATE 会永久删除表内数据，请谨慎使用。
"""
from typing import List
import importlib

# 脚本会默认删除的两张表：
#  - chengyu -> ['chengyu_relation', 'hanyuguoxue_chengyu']
#  - ciyu   -> ['ciyu_relation', 'hanyuguoxue_ciyu']
# 为了确保能清空父表，脚本**会始终禁用外键检查**。
TARGET_SOURCE = 'ciyu'  # 只修改这一项为 'chengyu' 或 'ciyu'
# =======================================================================


def _get_connection_for(source: str):
    """动态导入对应模块并返回 get_database_connection() 的结果。"""
    if source == 'chengyu':
        mod = importlib.import_module('chengyu.chengyu_mysql')
        return getattr(mod, 'get_database_connection')()
    if source == 'ciyu':
        mod = importlib.import_module('ciyu.ciyu_mysql')
        return getattr(mod, 'get_database_connection')()
    raise ValueError('未知的数据源: ' + source)


def clear_tables(tables: List[str], source: str = 'chengyu', interactive: bool = True) -> int:
    """清空指定 source 下的 tables。

    返回退出码：0 成功，非 0 失败/取消。
    """
    if interactive:
        print('\n' + '*' * 80)
        print(f"WARNING: 即将永久删除 {source} 数据库中的表: {tables}")
        print('如果你不确定，请按 Ctrl+C 取消。')
        print("要继续请输入 YES 并回车：", end='')
        try:
            confirm = input().strip()
        except Exception:
            print('\n未收到输入，已取消操作')
            return 4
        if confirm != 'YES':
            print('未输入 YES，已取消操作。')
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
    tables = _default_tables_for(TARGET_SOURCE)
    exit(clear_tables(tables, source=TARGET_SOURCE, interactive=True))
