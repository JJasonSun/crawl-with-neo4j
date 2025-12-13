# -*- coding: utf-8 -*-
"""
全局配置：数据库连接、TEST_MODE、通用默认值等。
"""
import os

# =====================
# 数据库配置
# =====================
# MySQL 连接配置
MYSQL_CONFIG = {
    "host": "8.153.207.172",
    "user": "root",
    "password": "Restart1128",
    "database": "lab_education",
    "port": 3307,
}

# Neo4j 连接配置
NEO4J_CONFIG = {
    "uri": "bolt://8.153.207.172:7687",
    "user": "neo4j",
    "password": "xtxzhu2u",
}

# 全局测试模式开关（若为 True，所有写库操作仅打印 SQL/计划，不实际写入）
TEST_MODE = True

# 日志控制配置
# 控制台日志输出级别：DEBUG, INFO, WARNING, ERROR，设置为 None 表示不输出到控制台
CONSOLE_LOG_LEVEL = None  # 禁用控制台日志输出，只保留文件日志

# =====================
# 通用默认值
# =====================
# 默认批处理大小：每次处理的记录数量
DEFAULT_BATCH_SIZE = 1000
# 默认请求延迟：每个详情页请求之间的延迟（秒）
DEFAULT_REQUEST_DELAY = 0.0
# 默认搜索延迟：每个搜索请求之间的延迟（秒）
DEFAULT_SEARCH_DELAY = 0.0
# 最大随机抖动：为避免请求模式被识别，添加的随机延迟上限（秒）
DEFAULT_JITTER_MAX = 0.8
# 优雅关闭等待时间：收到中断信号后等待正在进行的请求完成的时间（秒）
DEFAULT_GRACEFUL_SHUTDOWN_WAIT = 3.0
# 数据库批处理大小：批量写入数据库的记录数
DB_BATCH_SIZE = 50
# 数据库刷新间隔：批量写入数据库的时间间隔（秒）
DB_FLUSH_INTERVAL = 3.0
# 重试退避基数：失败重试的基础延迟时间（秒）
RETRY_BACKOFF_BASE = 300
# 重试退避上限：失败重试的最大延迟时间（秒）
RETRY_BACKOFF_MAX = 3600

# =====================
# 爬虫配置
# =====================
# 爬虫运行参数配置
CRAWLER_CONFIG = {
    "max_workers": 4,          # 最大工作线程数
    "timeout": 30,             # 请求超时时间（秒）
    "retry_times": 3,          # 重试次数
    "batch_size": 1000,        # 批处理大小
    "rate_limit": 1.0,         # 请求频率限制（秒）
}

# =====================
# 数据库连接测试
# =====================
def test_mysql_connection():
    """测试 MySQL 数据库连接"""
    if TEST_MODE:
        print("✓ 测试模式：MySQL 连接模拟成功")
        return True
        
    try:
        import pymysql
        cfg = MYSQL_CONFIG.copy()
        cfg.update({"charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor})
        conn = pymysql.connect(**cfg)
        cur = conn.cursor()
        cur.execute("SELECT VERSION() AS version")
        result = cur.fetchone()
        conn.close()
        print(f"✓ MySQL 连接成功")
        print(f"  版本: {result['version']}")
        print(f"  主机: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}")
        print(f"  数据库: {MYSQL_CONFIG['database']}")
        return True
    except Exception as e:
        print(f"✗ MySQL 连接失败: {e}")
        return False


def test_neo4j_connection():
    """测试 Neo4j 数据库连接"""
    if TEST_MODE:
        print("✓ 测试模式：Neo4j 连接模拟成功")
        return True
        
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            uri=NEO4J_CONFIG["uri"],
            auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"])
        )
        with driver.session() as session:
            result = session.run("RETURN 'Connection test successful' AS message")
            record = result.single()
            message = record["message"]
        driver.close()
        print(f"✓ Neo4j 连接成功")
        print(f"  URI: {NEO4J_CONFIG['uri']}")
        print(f"  用户: {NEO4J_CONFIG['user']}")
        print(f"  测试消息: {message}")
        return True
    except Exception as e:
        print(f"✗ Neo4j 连接失败: {e}")
        return False


def test_all_connections():
    """测试所有数据库连接"""
    print("=" * 60)
    print("数据库连接测试")
    print("=" * 60)
    
    mysql_ok = test_mysql_connection()
    print()
    neo4j_ok = test_neo4j_connection()
    print()
    
    if mysql_ok and neo4j_ok:
        print("✓ 所有数据库连接正常")
        return True
    else:
        print("✗ 部分数据库连接失败")
        return False


# =====================
# 数据库连接函数
# =====================
def get_mysql_connection():
    """获取MySQL数据库连接"""
    if TEST_MODE:
        print("测试模式：返回模拟MySQL连接")
        return {"test_mode": True}
    
    try:
        import pymysql
        cfg = MYSQL_CONFIG.copy()
        cfg.update({"charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor})
        return pymysql.connect(**cfg)
    except Exception as e:
        print(f"MySQL连接失败: {e}")
        return None


def get_neo4j_driver():
    """获取Neo4j数据库驱动"""
    if TEST_MODE:
        print("测试模式：返回模拟Neo4j驱动")
        return {"test_mode": True}
    
    try:
        from neo4j import GraphDatabase
        return GraphDatabase.driver(
            uri=NEO4J_CONFIG["uri"],
            auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"])
        )
    except Exception as e:
        print(f"Neo4j连接失败: {e}")
        return None


# =====================
# 路径工具
# =====================
def get_base_dir(subdir: str) -> str:
    """获取子目录的绝对路径（用于 CSV/pending 等文件定位）。"""
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..", subdir)))