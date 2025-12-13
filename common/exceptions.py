# -*- coding: utf-8 -*-
"""
自定义异常类
提供更细粒度的异常分类，便于错误处理和日志记录。
"""


class CrawlerBaseException(Exception):
    """爬虫基础异常"""
    def __init__(self, message: str, detail: str = None, error_code: int = None, **kwargs):
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.error_code = error_code
        # 存储额外的关键字参数
        for key, value in kwargs.items():
            setattr(self, key, value)


class ConfigurationException(CrawlerBaseException):
    """配置异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=6001, **kwargs)


class NetworkException(CrawlerBaseException):
    """网络相关异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=2001, **kwargs)


class ParseException(CrawlerBaseException):
    """解析异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=3001, **kwargs)


class DatabaseException(CrawlerBaseException):
    """数据库异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=5001, **kwargs)


class RateLimitException(NetworkException):
    """限流异常"""
    def __init__(self, message: str = "请求频率过高，触发限流", retry_after: int = None, **kwargs):
        # 不传递error_code给父类，因为NetworkException已经有默认的error_code
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        # 覆盖父类的error_code
        self.error_code = 4001


class NetworkOutageError(NetworkException):
    """网络中断异常"""
    def __init__(self, message: str = "网络连接中断"):
        super().__init__(message)


class TransientAccessError(NetworkException):
    """临时访问失败异常（需要退避重试）"""
    def __init__(self, message: str, detail: str = None, backoff_seconds: int = None):
        super().__init__(message, detail)
        self.backoff_seconds = backoff_seconds


class AuthenticationError(NetworkException):
    """认证失败异常"""
    pass


class ValidationError(ParseException):
    """数据验证异常"""
    pass


class ConfigurationError(CrawlerBaseException):
    """配置错误异常"""
    pass