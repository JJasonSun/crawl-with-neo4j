# -*- coding: utf-8 -*-
"""
统一日志管理模块
提供结构化日志记录和日志轮转功能。
"""
import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str, log_file: str, level: int = logging.INFO, 
                 max_bytes: int = 10*1024*1024, backup_count: int = 5, 
                 console_output: bool = True):
        """
        初始化结构化日志记录器
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径
            level: 日志级别
            max_bytes: 单个日志文件最大字节数
            backup_count: 保留的备份文件数量
            console_output: 是否输出到控制台
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            # 文件处理器（结构化JSON格式）
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_bytes, 
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(file_handler)
            
            # 控制台处理器（人类可读格式）
            if console_output:
                console_handler = logging.StreamHandler()
                console_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                console_handler.setFormatter(console_formatter)
                self.logger.addHandler(console_handler)
    
    def _log_structured(self, level: int, event: str, **kwargs):
        """记录结构化日志"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': logging.getLevelName(level),
            'event': event,
            **kwargs
        }
        
        # 文件记录使用JSON格式
        json_message = json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
        
        # 控制台记录使用人类可读格式
        console_message = f"{event}"
        if kwargs:
            details = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
            console_message += f" - {details}"
        
        # 记录到文件（JSON格式）
        self.logger.log(level, json_message)
        
        # 如果有控制台处理器，也记录到控制台（人类可读格式）
        if any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            # 创建一个临时的控制台消息记录器
            console_logger = logging.getLogger(f"{self.logger.name}_console")
            if not console_logger.handlers:
                console_handler = logging.StreamHandler()
                console_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                console_handler.setFormatter(console_formatter)
                console_logger.addHandler(console_handler)
                console_logger.setLevel(level)
            console_logger.log(level, console_message)
    
    def info(self, event: str, **kwargs):
        """记录信息级别日志"""
        self._log_structured(logging.INFO, event, **kwargs)
    
    def warning(self, event: str, **kwargs):
        """记录警告级别日志"""
        self._log_structured(logging.WARNING, event, **kwargs)
    
    def error(self, event: str, **kwargs):
        """记录错误级别日志"""
        self._log_structured(logging.ERROR, event, **kwargs)
    
    def debug(self, event: str, **kwargs):
        """记录调试级别日志"""
        self._log_structured(logging.DEBUG, event, **kwargs)
    
    def critical(self, event: str, **kwargs):
        """记录严重级别日志"""
        self._log_structured(logging.CRITICAL, event, **kwargs)
    
    # 专用日志方法
    def log_crawl_start(self, batch_id: int, total_items: int, crawler_name: str):
        """记录爬取开始"""
        self.info("crawl_start", 
                 batch_id=batch_id, 
                 total_items=total_items, 
                 crawler_name=crawler_name)
    
    def log_crawl_end(self, batch_id: int, success: int, failed: int, duration: float):
        """记录爬取结束"""
        self.info("crawl_end", 
                 batch_id=batch_id, 
                 success=success, 
                 failed=failed, 
                 duration=duration)
    
    def log_network_error(self, url: str, error: str, retry_count: int = 0):
        """记录网络错误"""
        self.error("network_error", 
                  url=url, 
                  error=error, 
                  retry_count=retry_count)
    
    def log_parse_error(self, url: str, error: str):
        """记录解析错误"""
        self.error("parse_error", url=url, error=error)
    
    def log_database_error(self, operation: str, error: str):
        """记录数据库错误"""
        self.error("database_error", operation=operation, error=error)
    
    def log_rate_limit(self, url: str, retry_after: int = None):
        """记录限流"""
        self.warning("rate_limit", url=url, retry_after=retry_after)
    
    # 测试中期望的方法
    def crawl_error(self, *args, **kwargs):
        """记录爬取错误（测试兼容）"""
        if len(args) >= 3:
            # 测试中的调用方式: crawl_error('chengyu', 'http://test.com', 'timeout')
            data_type, url, error_type = args[0], args[1], args[2]
            self.error("crawl_error", data_type=data_type, url=url, error_type=error_type, **kwargs)
        else:
            # 标准调用方式
            message = args[0] if args else "crawl_error"
            self.error("crawl_error", message=message, **kwargs)
    
    def crawl_start(self, *args, **kwargs):
        """记录爬取开始（测试兼容）"""
        if len(args) >= 2:
            # 测试中的调用方式: crawl_start('chengyu', 100)
            data_type, total_count = args[0], args[1]
            self.info("crawl_start", data_type=data_type, total_count=total_count, **kwargs)
        else:
            # 标准调用方式
            message = args[0] if args else "crawl_start"
            self.info("crawl_start", message=message, **kwargs)
    
    def crawl_success(self, *args, **kwargs):
        """记录爬取成功（测试兼容）"""
        if len(args) >= 3:
            # 测试中的调用方式: crawl_success('chengyu', 95, 5)
            data_type, success_count, error_count = args[0], args[1], args[2]
            self.info("crawl_success", data_type=data_type, success_count=success_count, error_count=error_count, **kwargs)
        else:
            # 标准调用方式
            message = args[0] if args else "crawl_success"
            self.info("crawl_success", message=message, **kwargs)
    
    def db_operation(self, *args, **kwargs):
        """记录数据库操作（测试兼容）"""
        if len(args) >= 4:
            # 测试中的调用方式: db_operation('insert', 'chengyu', 1, True)
            operation, table, record_id, success = args[0], args[1], args[2], args[3]
            self.info("db_operation", operation=operation, table=table, record_id=record_id, success=success, **kwargs)
        else:
            # 标准调用方式
            message = args[0] if args else "db_operation"
            self.info("db_operation", message=message, **kwargs)


def get_logger(name: str, log_dir: str = "logs", console_output: bool = None) -> StructuredLogger:
    """获取日志记录器实例
    
    Args:
        name: 日志记录器名称
        log_dir: 日志目录
        console_output: 是否输出到控制台，默认为None（从配置读取）
    
    Returns:
        StructuredLogger: 日志记录器实例
    """
    # 如果没有明确指定，则从配置读取
    if console_output is None:
        try:
            from common.config import CONSOLE_LOG_LEVEL
            console_output = CONSOLE_LOG_LEVEL is not None
        except ImportError:
            console_output = True
    
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name}.log")
    return StructuredLogger(name, log_file, console_output=console_output)