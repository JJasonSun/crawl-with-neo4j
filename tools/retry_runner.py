# -*- coding: utf-8 -*-
"""
通用错误重试调度：读取 batch_*_errors.csv，重新抓取并写库。
"""
from __future__ import annotations

import csv
import glob
import time
from typing import Any, Callable, Dict, List, Tuple

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.crawl_runner import CrawlerConfig

# 导入自定义异常和日志系统
from common.exceptions import (
    NetworkException, ParseException, RateLimitException,
    DatabaseException, CrawlerBaseException
)
from common.logger import get_logger


def read_error_items(cfg: CrawlerConfig, key_name: str) -> List[Tuple[str, str, str]]:
    """读取错误文件中的项目列表
    
    Args:
        cfg: 爬虫配置对象
        key_name: 键名（chengyu 或 ciyu）
    
    Returns:
        List[Tuple[str, str, str]]: (项目, 错误信息, 文件名) 的元组列表
    """
    # 初始化日志器
    logger = get_logger(f"retry_reader_{cfg.name}")
    
    items: List[Tuple[str, str, str]] = []
    pattern = os.path.join(cfg.base_dir, "batch_*_errors.csv")
    error_files = glob.glob(pattern)
    
    logger.info("开始读取错误文件", extra_data={
        'pattern': pattern,
        'file_count': len(error_files)
    })
    
    for error_file in error_files:
        try:
            with open(error_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                file_items = 0
                for row in reader:
                    item = (row.get(key_name, "") or "").strip()
                    error = (row.get("error", "") or "").strip()
                    if item:
                        items.append((item, error, os.path.basename(error_file)))
                        file_items += 1
                
                logger.debug("已读取错误文件", extra_data={
                    'file': error_file,
                    'item_count': file_items
                })
        except Exception as exc:  # noqa: BLE001
            logger.error("读取错误文件失败", extra_data={
                'file': error_file,
                'exception_type': type(exc).__name__,
                'exception_message': str(exc)
            })
            print(f"读取错误文件 {error_file} 失败: {exc}")
    
    logger.info("错误文件读取完成", extra_data={'total_items': len(items)})
    return items


def retry_item(
    item: str,
    delay: float,
    search_func: Callable[[str, float, Any], Any],
    detail_func: Callable[[str, float, Any], Dict],
    save_func: Callable[[Dict], bool],
    key_name: str,
):
    """重试单个项目的爬取
    
    Args:
        item: 要重试的项目
        delay: 请求延迟（秒）
        search_func: 搜索函数
        detail_func: 详情页解析函数
        save_func: 数据保存函数
        key_name: 键名（chengyu 或 ciyu）
    
    Returns:
        Tuple[bool, str]: (是否成功, 错误信息)
    """
    # 初始化日志器
    logger = get_logger(f"retry_item_{key_name}")
    
    try:
        import requests
        time.sleep(delay)
        session = requests.Session()
        
        logger.debug("开始重试搜索", extra_data={'item': item})
        url_result = search_func(item, delay, session)
        if isinstance(url_result, dict) and url_result.get("error"):
            error_msg = f"获取URL失败: {url_result.get('error')}"
            logger.error("搜索失败", extra_data={
                'item': item,
                'error': url_result.get('error')
            })
            return False, error_msg
        url = url_result
        if url is None:
            error_msg = "无法获取详情页URL"
            logger.error("未获取到URL", extra_data={'item': item})
            return False, error_msg

        time.sleep(delay)
        # 确保传递给detail_func的是字符串
        url_str = url if isinstance(url, str) else str(url)
        
        logger.debug("开始重试详情页解析", extra_data={
            'item': item,
            'url': url_str
        })
        data = detail_func(url_str, delay, session)
        if isinstance(data, dict) and "error" in data:
            error_msg = f"提取详情失败: {data.get('error')}"
            logger.error("详情页解析失败", extra_data={
                'item': item,
                'url': url_str,
                'error': data.get('error')
            })
            return False, error_msg

        if not isinstance(data, dict):
            logger.warning("数据格式异常，使用默认格式", extra_data={
                'item': item,
                'url': url_str,
                'data_type': type(data).__name__
            })
            data = {"url": url, "data": {key_name: item}}
        else:
            if "data" not in data or not data.get("data"):
                data = {"url": url, "data": {key_name: item}}
            else:
                if not data["data"].get(key_name):
                    data["data"][key_name] = item
                    logger.debug("添加缺失的标签", extra_data={
                        'item': item,
                        'key_name': key_name
                    })

        logger.debug("开始保存数据", extra_data={
            'item': item,
            'url': url
        })
        success = save_func(data)
        if success:
            logger.info("重试成功", extra_data={
                'item': item,
                'url': url
            })
            return True, "成功保存到数据库"
        else:
            logger.error("保存到数据库失败", extra_data={
                'item': item,
                'url': url
            })
            return False, "保存到数据库失败"
    except Exception as exc:  # noqa: BLE001
        logger.error("处理异常", extra_data={
            'item': item,
            'exception_type': type(exc).__name__,
            'exception_message': str(exc)
        })
        return False, f"处理异常: {exc}"


def run_retry(cfg: CrawlerConfig, key_name: str, delay: float = 1.5):
    """运行错误重试程序
    
    Args:
        cfg: 爬虫配置对象
        key_name: 键名（chengyu 或 ciyu）
        delay: 请求延迟（秒）
    
    Returns:
        int: 处理的项目数量
    """
    # 初始化日志器
    logger = get_logger(f"retry_main_{cfg.name}")
    
    logger.info("开始处理错误条目", extra_data={'delay': delay})
    print("开始处理错误条目...")
    
    items = read_error_items(cfg, key_name)
    if not items:
        logger.info("没有找到错误文件或文件为空")
        print("没有找到错误文件或文件为空")
        return 0

    logger.info("找到错误条目", extra_data={'count': len(items)})
    print(f"找到 {len(items)} 个错误条目")
    
    success_count = 0
    fail_count = 0
    results = []

    for idx, (item, original_error, file_name) in enumerate(items, 1):
        logger.info("处理错误条目", extra_data={
            'idx': idx,
            'total': len(items),
            'item': item,
            'file_name': file_name,
            'original_error': original_error[:100]
        })
        
        print(f"\n[{idx}/{len(items)}] 处理: {item} (来自 {file_name})")
        print(f"原错误: {original_error[:100]}...")
        
        ok, msg = retry_item(item, delay, cfg.search_func, cfg.detail_func, cfg.save_func, key_name)
        if ok:
            logger.info("重试成功", extra_data={
                'item': item,
                'message': msg
            })
            print(f"✓ 成功: {msg}")
            success_count += 1
        else:
            logger.error("重试失败", extra_data={
                'item': item,
                'message': msg
            })
            print(f"✗ 失败: {msg}")
            fail_count += 1
        results.append((item, original_error, file_name, ok, msg))

    result_file = os.path.join(cfg.base_dir, "retry_results.csv")
    with open(result_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([key_name, "original_error", "source_file", "retry_success", "retry_message"])
        for row in results:
            writer.writerow(row)
    
    logger.info("重试完成", extra_data={
        'result_file': result_file,
        'success_count': success_count,
        'fail_count': fail_count,
        'total_count': len(items)
    })
    
    print(f"重试结果已保存到: {result_file}")
    print(f"成功: {success_count} / 失败: {fail_count} / 总计: {len(items)}")
    
    return len(items)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python retry_runner.py <chengyu|ciyu> [delay]")
        sys.exit(1)
    
    data_type = sys.argv[1]
    if data_type not in ["chengyu", "ciyu"]:
        print("错误: 数据类型必须是 'chengyu' 或 'ciyu'")
        sys.exit(1)
    
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    
    # 根据数据类型创建配置
    if data_type == "chengyu":
        from chengyu.extract_chengyu import build_crawler_config
        cfg = build_crawler_config()
    else:
        from ciyu.extract_ciyu import build_crawler_config
        cfg = build_crawler_config()
    
    # 运行重试
    processed = run_retry(cfg, data_type, delay)
    sys.exit(0 if processed > 0 else 0)
