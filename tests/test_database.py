# -*- coding: utf-8 -*-
"""
数据库操作测试
测试成语和词语数据库操作的基本功能。
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chengyu.chengyu_DB import ChengyuDB
from ciyu.ciyu_DB import CiyuDB
from common.config import TEST_MODE


class TestChengyuDB(unittest.TestCase):
    """成语数据库操作测试"""
    
    def setUp(self):
        """测试前准备"""
        # 确保测试模式开启
        import common.config
        self.original_test_mode = common.config.TEST_MODE
        common.config.TEST_MODE = True
        
        self.db = ChengyuDB()
        self.test_data = {
            'url': 'http://test.com/chengyu/1',
            'data': {
                'chengyu': '一帆风顺',
                'pinyin': 'yī fān fēng shùn',
                'explanation': '船挂着满帆顺风行驶。比喻事情非常顺利，没有阻碍。',
                'synonyms': ["顺风顺水", "一路顺风"],
                'antonyms': ["一波三折", "崎岖不平"]
            }
        }
    
    def tearDown(self):
        """测试后清理"""
        # 恢复原始测试模式
        import common.config
        common.config.TEST_MODE = self.original_test_mode
    
    def test_get_main_table_name(self):
        """测试获取主表名"""
        self.assertEqual(self.db.get_main_table_name(), "hanyuguoxue_chengyu")
    
    def test_get_relation_table_name(self):
        """测试获取关系表名"""
        self.assertEqual(self.db.get_relation_table_name(), "chengyu_relation")
    
    def test_get_main_key_field(self):
        """测试获取主键字段名"""
        self.assertEqual(self.db.get_main_key_field(), "chengyu")
    
    def test_get_label_key(self):
        """测试获取标签键名"""
        self.assertEqual(self.db.get_label_key(), "chengyu")
    
    def test_get_neo4j_label(self):
        """测试获取Neo4j标签名"""
        self.assertEqual(self.db.get_neo4j_label(), "Idiom")
    
    def test_save_to_mysql_success(self):
        """测试成功保存到MySQL"""
        # 创建数据库实例并设置非测试模式
        self.db = ChengyuDB()
        self.db.test_mode = False
        
        # 模拟数据库连接和游标
        with patch.object(self.db, 'get_mysql_connection') as mock_get_connection:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {'id': 1}
            mock_get_connection.return_value = mock_conn
            
            result = self.db.save_to_mysql(self.test_data)
            self.assertTrue(result)
            
            # 检查mock是否被调用
            mock_get_connection.assert_called_once()
            mock_conn.cursor.assert_called_once()
            mock_cursor.execute.assert_called()
            mock_conn.commit.assert_called()
    
    def test_save_to_mysql_error(self):
        """测试保存失败情况"""
        # 创建数据库实例并设置非测试模式
        self.db = ChengyuDB()
        self.db.test_mode = False
        
        with patch.object(self.db, 'get_mysql_connection') as mock_get_connection:
            mock_get_connection.return_value = None
            
            result = self.db.save_to_mysql(self.test_data)
            self.assertFalse(result)
            
            # 检查mock是否被调用
            mock_get_connection.assert_called_once()
    
    def test_save_to_mysql_test_mode(self):
        """测试测试模式下的保存"""
        # 在测试模式下，save_to_mysql 应该返回 True
        result = self.db.save_to_mysql(self.test_data)
        self.assertTrue(result)


class TestCiyuDB(unittest.TestCase):
    """词语数据库操作测试"""
    
    def setUp(self):
        """测试前准备"""
        # 确保测试模式开启
        import common.config
        self.original_test_mode = common.config.TEST_MODE
        common.config.TEST_MODE = True
        
        self.db = CiyuDB()
        self.test_data = {
            'url': 'http://test.com/ciyu/1',
            'data': {
                'ciyu': '学习',
                'pinyin': 'xué xí',
                'explanation': '从阅读、听讲、研究、实践中获得知识或技能。',
                'synonyms': ["进修", "研习"],
                'antonyms': ["荒废", "放弃"]
            }
        }
    
    def tearDown(self):
        """测试后清理"""
        # 恢复原始测试模式
        import common.config
        common.config.TEST_MODE = self.original_test_mode
    
    def test_get_main_table_name(self):
        """测试获取主表名"""
        self.assertEqual(self.db.get_main_table_name(), "hanyuguoxue_ciyu")
    
    def test_get_relation_table_name(self):
        """测试获取关系表名"""
        self.assertEqual(self.db.get_relation_table_name(), "ciyu_relation")
    
    def test_get_main_key_field(self):
        """测试获取主键字段名"""
        self.assertEqual(self.db.get_main_key_field(), "ciyu")
    
    def test_get_label_key(self):
        """测试获取标签键名"""
        self.assertEqual(self.db.get_label_key(), "ciyu")
    
    def test_get_neo4j_label(self):
        """测试获取Neo4j标签名"""
        self.assertEqual(self.db.get_neo4j_label(), "Word")
    
    def test_save_to_mysql_success(self):
        """测试成功保存到MySQL"""
        # 创建新的数据库实例并设置非测试模式
        db = CiyuDB()
        db.test_mode = False
        
        # 模拟数据库连接和游标
        with patch.object(db, 'get_mysql_connection') as mock_get_connection:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {'id': 1}
            mock_get_connection.return_value = mock_conn
            
            result = db.save_to_mysql(self.test_data)
            self.assertTrue(result)
            
            # 检查mock是否被调用
            mock_get_connection.assert_called_once()
            mock_conn.cursor.assert_called_once()
            mock_cursor.execute.assert_called()
            mock_conn.commit.assert_called()
    
    def test_save_to_mysql_test_mode(self):
        """测试测试模式下的保存"""
        # 确保测试模式开启并创建新的数据库实例
        import common.config
        common.config.TEST_MODE = True
        db = CiyuDB()
        
        # 在测试模式下，save_to_mysql 应该返回 True
        result = db.save_to_mysql(self.test_data)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()