#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接测试工具

测试真实的 MySQL 和 Neo4j 数据库连接状态。

用法：
    python tests/test_connections.py          # 测试所有连接
    python tests/test_connections.py mysql     # 只测试 MySQL
    python tests/test_connections.py neo4j    # 只测试 Neo4j
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import test_mysql_connection, test_neo4j_connection, test_all_connections


def main():
    """主函数"""
    # 禁用测试模式，使用真实连接
    import common.config
    original_test_mode = common.config.TEST_MODE
    common.config.TEST_MODE = False
    
    try:
        if len(sys.argv) > 1:
            db_type = sys.argv[1].lower()
            
            if db_type == 'mysql':
                print("=" * 60)
                print("MySQL 连接测试")
                print("=" * 60)
                success = test_mysql_connection()
                return 0 if success else 1
                
            elif db_type == 'neo4j':
                print("=" * 60)
                print("Neo4j 连接测试")
                print("=" * 60)
                success = test_neo4j_connection()
                return 0 if success else 1
                
            else:
                print("用法:")
                print("  python tests/test_connections.py          # 测试所有连接")
                print("  python tests/test_connections.py mysql     # 只测试 MySQL")
                print("  python tests/test_connections.py neo4j    # 只测试 Neo4j")
                return 1
        else:
            # 测试所有连接
            success = test_all_connections()
            return 0 if success else 1
    finally:
        # 恢复原始测试模式
        common.config.TEST_MODE = original_test_mode


if __name__ == '__main__':
    sys.exit(main())