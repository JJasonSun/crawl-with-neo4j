# -*- coding: utf-8 -*-
"""
此脚本会永久删除两张表中的所有数据：
  - chengyu_relation
  - hanyuguoxue_chengyu

强烈警告：
  - 该操作不可逆（除非你有数据库备份）。
  - 请仅在你确定要完全重建数据库并已做好备份时运行。
  - 运行时需要手动确认（输入 YES）以防止误执行。

示例：
  python clear_crawled_data.py

"""

from chengyu_mysql import get_database_connection


def main(interactive=True):
    """
    清空成语表数据。默认启用交互确认（需要输入 YES 才会继续）。
    若在非交互环境中运行，可传入 interactive=False，但请非常小心。
    """
    if interactive:
        print('\n' + '*' * 80)
        print('WARNING: 即将永久删除 chengyu_relation 和 hanyuguoxue_chengyu 中的所有数据。')
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

    conn = get_database_connection()
    if not conn:
        print('无法连接到数据库，退出')
        return 2
    cur = conn.cursor()
    try:
        print('开始清理 chengyu_relation ...')
        cur.execute('TRUNCATE TABLE chengyu_relation')
        print('已清理 chengyu_relation')
        print('开始清理 hanyuguoxue_chengyu ...')
        # 为了能够清空父表，临时关闭外键检查
        cur.execute('SET FOREIGN_KEY_CHECKS=0')
        cur.execute('TRUNCATE TABLE hanyuguoxue_chengyu')
        cur.execute('SET FOREIGN_KEY_CHECKS=1')
        print('已清理 hanyuguoxue_chengyu')
        conn.commit()
        return 0
    except Exception as e:
        print('清理失败:', e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 3
    finally:
        conn.close()


if __name__ == '__main__':
    exit(main())
