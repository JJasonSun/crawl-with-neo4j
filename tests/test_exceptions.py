# -*- coding: utf-8 -*-
"""
异常处理测试
测试自定义异常类的功能。
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.exceptions import (
    CrawlerBaseException, NetworkException, ParseException,
    RateLimitException, DatabaseException, ConfigurationException
)


class TestCrawlerExceptions(unittest.TestCase):
    """爬虫异常测试"""
    
    def test_crawler_base_exception(self):
        """测试基础异常类"""
        # 测试基本异常
        exc = CrawlerBaseException("Test message")
        self.assertEqual(str(exc), "Test message")
        self.assertEqual(exc.message, "Test message")
        self.assertIsNone(exc.error_code)
        
        # 测试带错误码的异常
        exc = CrawlerBaseException("Test message", error_code=1001)
        self.assertEqual(str(exc), "Test message")
        self.assertEqual(exc.message, "Test message")
        self.assertEqual(exc.error_code, 1001)
        
        # 测试带额外数据的异常
        exc = CrawlerBaseException("Test message", extra_data={'key': 'value'})
        self.assertEqual(str(exc), "Test message")
        self.assertEqual(exc.message, "Test message")
        self.assertEqual(exc.extra_data['key'], 'value')
    
    def test_network_exception(self):
        """测试网络异常"""
        exc = NetworkException("Network timeout", url="http://test.com", status_code=408)
        self.assertEqual(str(exc), "Network timeout")
        self.assertEqual(exc.url, "http://test.com")
        self.assertEqual(exc.status_code, 408)
        self.assertEqual(exc.error_code, 2001)
    
    def test_parse_exception(self):
        """测试解析异常"""
        exc = ParseException("Parse error", url="http://test.com", selector=".content")
        self.assertEqual(str(exc), "Parse error")
        self.assertEqual(exc.url, "http://test.com")
        self.assertEqual(exc.selector, ".content")
        self.assertEqual(exc.error_code, 3001)
    
    def test_rate_limit_exception(self):
        """测试限流异常"""
        exc = RateLimitException("Rate limit exceeded", retry_after=60)
        self.assertEqual(str(exc), "Rate limit exceeded")
        self.assertEqual(exc.retry_after, 60)
        self.assertEqual(exc.error_code, 4001)
    
    def test_database_exception(self):
        """测试数据库异常"""
        exc = DatabaseException("Database connection failed", operation="connect", table="chengyu")
        self.assertEqual(str(exc), "Database connection failed")
        self.assertEqual(exc.operation, "connect")
        self.assertEqual(exc.table, "chengyu")
        self.assertEqual(exc.error_code, 5001)
    
    def test_configuration_exception(self):
        """测试配置异常"""
        exc = ConfigurationException("Invalid config", config_key="mysql.host")
        self.assertEqual(str(exc), "Invalid config")
        self.assertEqual(exc.config_key, "mysql.host")
        self.assertEqual(exc.error_code, 6001)
    
    def test_exception_inheritance(self):
        """测试异常继承关系"""
        # 所有自定义异常都应该继承自CrawlerBaseException
        self.assertTrue(issubclass(NetworkException, CrawlerBaseException))
        self.assertTrue(issubclass(ParseException, CrawlerBaseException))
        self.assertTrue(issubclass(RateLimitException, CrawlerBaseException))
        self.assertTrue(issubclass(DatabaseException, CrawlerBaseException))
        self.assertTrue(issubclass(ConfigurationException, CrawlerBaseException))
        
        # 所有自定义异常都应该继承自Python的Exception
        self.assertTrue(issubclass(NetworkException, Exception))
        self.assertTrue(issubclass(ParseException, Exception))
        self.assertTrue(issubclass(RateLimitException, Exception))
        self.assertTrue(issubclass(DatabaseException, Exception))
        self.assertTrue(issubclass(ConfigurationException, Exception))
    
    def test_exception_error_codes(self):
        """测试异常错误码"""
        # 验证错误码在预期范围内
        self.assertEqual(NetworkException("Test").error_code, 2001)
        self.assertEqual(ParseException("Test").error_code, 3001)
        self.assertEqual(RateLimitException("Test").error_code, 4001)
        self.assertEqual(DatabaseException("Test").error_code, 5001)
        self.assertEqual(ConfigurationException("Test").error_code, 6001)
    
    def test_exception_with_all_parameters(self):
        """测试带所有参数的异常"""
        exc = NetworkException(
            "Complex error",
            url="http://test.com",
            status_code=500,
            extra_data={'response': 'error'}
        )
        # 手动设置错误码以避免冲突
        exc.error_code = 9999
        
        self.assertEqual(str(exc), "Complex error")
        self.assertEqual(exc.error_code, 9999)
        self.assertEqual(exc.url, "http://test.com")
        self.assertEqual(exc.status_code, 500)
        self.assertEqual(exc.extra_data['response'], 'error')


if __name__ == '__main__':
    unittest.main()