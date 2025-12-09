# chengyu/test_db_connect.py
"""
集中的 MySQL 连接模块，同时包含一个运行测试的入口。

功能：
 - 导出 `mysql_config` 和 `get_database_connection()` 供其他模块导入使用
 - 作为脚本运行时会尝试建立连接并打印 MySQL 版本（便于快速连通性测试）

示例：
    python test_db_connect.py
"""
import pymysql

# MySQL数据库配置
mysql_config = {
    "host": "8.153.207.172",
    "user": "root",
    "password": "Restart1128",
    "database": "lab_education",
    "port": 3307
}


def get_database_connection():
    """
    获取 MySQL 数据库连接（返回 pymysql.Connection 或 None）。
    """
    try:
        connection = pymysql.connect(
            host=mysql_config["host"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
            port=mysql_config["port"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"无法建立数据库连接: {e}")
        return None


def main():
    conn = get_database_connection()
    if not conn:
        print("无法建立连接")
        return 2
    try:
        cur = conn.cursor()
        cur.execute("SELECT VERSION() AS v;")
        print("数据库可达，版本：", cur.fetchone())
    except Exception as e:
        print("执行测试查询失败：", e)
        return 3
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    exit(main())