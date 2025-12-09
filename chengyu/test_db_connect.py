# chengyu/test_db_connect.py
from hanyuguoxue_chengyu import get_database_connection

conn = get_database_connection()
if not conn:
    print("无法建立连接")
else:
    try:
        cur = conn.cursor()
        cur.execute("SELECT VERSION() AS v;")
        print("数据库可达，版本：", cur.fetchone())
    except Exception as e:
        print("执行测试查询失败：", e)
    finally:
        conn.close()