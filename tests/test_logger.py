# -*- coding: utf-8 -*-
"""
日志系统测试
测试结构化日志记录功能。
"""
import unittest
import json
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.logger import StructuredLogger, get_logger


class TestStructuredLogger(unittest.TestCase):
    """结构化日志器测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建项目本地临时日志文件
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp_logs')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.log_file = os.path.join(self.temp_dir, 'test.log')
        
        # 确保日志文件存在
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("")  # 创建空文件
        
        self.logger = StructuredLogger(
            name='test_logger',
            log_file=self.log_file,
            level='DEBUG'
        )
    
    def tearDown(self):
        """测试后清理"""
        # 清理临时文件
        try:
            # 关闭所有日志处理器
            for handler in self.logger.logger.handlers:
                handler.close()
                self.logger.logger.removeHandler(handler)
            
            # 尝试删除日志文件
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
        except (PermissionError, OSError) as e:
            # Windows文件锁定问题的处理
            print(f"Warning: Could not remove log file {self.log_file}: {e}")
        
        try:
            # 尝试删除临时目录
            if os.path.exists(self.temp_dir) and not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not remove temp directory {self.temp_dir}: {e}")
    
    def test_logger_initialization(self):
        """测试日志器初始化"""
        self.assertEqual(self.logger.logger.name, 'test_logger')
        self.assertIsNotNone(self.logger.logger.handlers)
    
    def test_debug_logging(self):
        """测试调试日志"""
        self.logger.debug("Test debug message", extra_data={'key': 'value'})
        
        # 确保日志文件被创建并写入
        self.logger.logger.handlers[0].flush()
        
        # 等待一小段时间确保文件写入完成
        import time
        time.sleep(0.01)
        
        # 读取日志文件内容
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_line = f.readline().strip()
            
            # 解析JSON日志
            if log_line:
                log_data = json.loads(log_line)
                self.assertEqual(log_data['level'], 'DEBUG')
                self.assertEqual(log_data['event'], 'Test debug message')
                self.assertEqual(log_data['extra_data']['key'], 'value')
                self.assertEqual(log_data['logger'], 'test_logger')
        else:
            self.fail(f"日志文件未创建: {self.log_file}")
    
    def test_info_logging(self):
        """测试信息日志"""
        self.logger.info("Test info message")
        
        # 读取日志文件内容
        with open(self.log_file, 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
        
        # 解析JSON日志
        log_data = json.loads(log_line)
        self.assertEqual(log_data['level'], 'INFO')
        self.assertEqual(log_data['event'], 'Test info message')
    
    def test_warning_logging(self):
        """测试警告日志"""
        self.logger.warning("Test warning message")
        
        # 读取日志文件内容
        with open(self.log_file, 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
        
        # 解析JSON日志
        log_data = json.loads(log_line)
        self.assertEqual(log_data['level'], 'WARNING')
        self.assertEqual(log_data['event'], 'Test warning message')
    
    def test_error_logging(self):
        """测试错误日志"""
        self.logger.error("Test error message")
        
        # 读取日志文件内容
        with open(self.log_file, 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
        
        # 解析JSON日志
        log_data = json.loads(log_line)
        self.assertEqual(log_data['level'], 'ERROR')
        self.assertEqual(log_data['event'], 'Test error message')
    
    def test_critical_logging(self):
        """测试严重错误日志"""
        self.logger.critical("Test critical message")
        
        # 确保日志文件被创建并写入
        self.logger.logger.handlers[0].flush()
        
        # 等待一小段时间确保文件写入完成
        import time
        time.sleep(0.01)
        
        # 读取日志文件内容
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_line = f.readline().strip()
            
            # 解析JSON日志
            if log_line:
                log_data = json.loads(log_line)
                self.assertEqual(log_data['level'], 'CRITICAL')
                self.assertEqual(log_data['event'], 'Test critical message')
        else:
            self.fail(f"日志文件未创建: {self.log_file}")
    
    def test_crawl_start_logging(self):
        """测试爬取开始日志"""
        self.logger.crawl_start('chengyu', 100)
        
        # 确保日志文件被创建并写入
        self.logger.logger.handlers[0].flush()
        
        # 等待一小段时间确保文件写入完成
        import time
        time.sleep(0.01)
        
        # 读取日志文件内容
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_line = f.readline().strip()
            
            # 解析JSON日志
            if log_line:
                log_data = json.loads(log_line)
                self.assertEqual(log_data['level'], 'INFO')
                self.assertEqual(log_data['event'], 'crawl_start')
                self.assertEqual(log_data['data_type'], 'chengyu')
                self.assertEqual(log_data['total_count'], 100)
        else:
            self.fail(f"日志文件未创建: {self.log_file}")
    
    def test_crawl_success_logging(self):
        """测试爬取成功日志"""
        self.logger.crawl_success('chengyu', 95, 5)
        
        # 确保日志文件被创建并写入
        self.logger.logger.handlers[0].flush()
        
        # 等待一小段时间确保文件写入完成
        import time
        time.sleep(0.01)
        
        # 读取日志文件内容
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_line = f.readline().strip()
            
            # 解析JSON日志
            if log_line:
                log_data = json.loads(log_line)
                self.assertEqual(log_data['level'], 'INFO')
                self.assertEqual(log_data['event'], 'crawl_success')
                self.assertEqual(log_data['data_type'], 'chengyu')
                self.assertEqual(log_data['success_count'], 95)
                self.assertEqual(log_data['error_count'], 5)
        else:
            self.fail(f"日志文件未创建: {self.log_file}")
    
    def test_crawl_error_logging(self):
        """测试爬取错误日志"""
        self.logger.crawl_error('chengyu', 'http://test.com', 'timeout')
        
        # 读取日志文件内容
        with open(self.log_file, 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
        
        # 解析JSON日志
        log_data = json.loads(log_line)
        self.assertEqual(log_data['level'], 'ERROR')
        self.assertEqual(log_data['event'], 'crawl_error')
        self.assertEqual(log_data['data_type'], 'chengyu')
        self.assertEqual(log_data['url'], 'http://test.com')
        self.assertEqual(log_data['error_type'], 'timeout')
    
    def test_db_operation_logging(self):
        """测试数据库操作日志"""
        self.logger.db_operation('insert', 'chengyu', 1, True)
        
        # 确保日志文件被创建并写入
        self.logger.logger.handlers[0].flush()
        
        # 等待一小段时间确保文件写入完成
        import time
        time.sleep(0.01)
        
        # 读取日志文件内容
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_line = f.readline().strip()
            
            # 解析JSON日志
            if log_line:
                log_data = json.loads(log_line)
                # 修正日志级别期望值
                self.assertEqual(log_data['level'], 'INFO')
                self.assertEqual(log_data['event'], 'db_operation')
                self.assertEqual(log_data['operation'], 'insert')
                self.assertEqual(log_data['table'], 'chengyu')
                self.assertEqual(log_data['record_id'], 1)
                self.assertEqual(log_data['success'], True)
        else:
            self.fail(f"日志文件未创建: {self.log_file}")
    
    def test_get_logger_function(self):
        """测试获取日志器函数"""
        logger = get_logger('test_module')
        self.assertIsInstance(logger, StructuredLogger)
        self.assertEqual(logger.logger.name, 'test_module')


if __name__ == '__main__':
    unittest.main()