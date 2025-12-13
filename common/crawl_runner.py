# -*- coding: utf-8 -*-
"""
通用批量爬取调度器：处理断点续爬、pending、后台写库、指标与错误输出。
适配 chengyu / ciyu 等不同领域，仅需在各自的 extract_*.py 中提供配置。
"""
from __future__ import annotations

import csv
import json
import os
import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

# 导入自定义异常和日志系统
from common.exceptions import (
    NetworkException, ParseException, RateLimitException,
    DatabaseException, CrawlerBaseException
)
from common.logger import get_logger

# =====================
# 异常定义（保持向后兼容）
# =====================
class NetworkOutageError(Exception):
    """表示网络异常未恢复，需要停止本批次并等待人为重启。"""


class TransientAccessError(Exception):
    """用于表示需要退避重试的临时访问失败（断网、封禁等）。"""

    def __init__(self, detail: Optional[str] = None):
        super().__init__(detail)
        self.detail = detail


# =====================
# 配置结构
# =====================
@dataclass
class CrawlerConfig:
    name: str  # 爬虫名称（用于日志和文件名）
    base_dir: str  # 基础目录路径
    get_items: Callable[[], List[str]]  # 获取待处理项目列表的函数
    search_func: Callable[[str, float, requests.Session], Any]  # 搜索函数
    detail_func: Callable[[str, float, requests.Session], Dict[str, Any]]  # 详情页解析函数
    save_func: Callable[[Dict[str, Any]], bool]  # 数据保存函数
    label_key: str  # 数据标签键名
    csv_filename: str = "batch_metrics.csv"  # 批次指标文件名
    pending_filename: str = "pending.json"  # 待处理项目文件名
    db_batch_size: int = 50  # 数据库批处理大小
    db_flush_interval: float = 3.0  # 数据库刷新间隔（秒）
    default_batch_size: int = 1000  # 默认批处理大小
    default_request_delay: float = 0.0  # 默认请求延迟（秒）
    default_search_delay: float = 0.0  # 默认搜索延迟（秒）
    default_jitter_max: float = 0.8  # 最大随机抖动（秒）
    default_graceful_wait: float = 3.0  # 优雅关闭等待时间（秒）
    retry_backoff_base: int = 300  # 重试退避基数（秒）
    retry_backoff_max: int = 3600  # 重试退避上限（秒）

    def csv_path(self) -> str:
        return os.path.join(self.base_dir, self.csv_filename)

    def pending_path(self) -> str:
        return os.path.join(self.base_dir, self.pending_filename)


# =====================
# 工具函数
# =====================
def _compute_backoff_delay(base: int, max_delay: int, attempt: int) -> int:
    try:
        return min(base * (2 ** attempt), max_delay)
    except OverflowError:
        return max_delay


def _retry_with_backoff(action: Callable[[], Any], label: str, base: int, max_delay: int):
    attempt = 0
    waited_max_delay = False
    while True:
        try:
            return action()
        except TransientAccessError as exc:  # type: ignore[assignment]
            detail_suffix = f" ({exc.detail})" if getattr(exc, "detail", None) else ""
            delay = _compute_backoff_delay(base, max_delay, attempt)
            msg = f"检测到{label}{detail_suffix}, 第 {attempt+1} 次重试，等待 {delay}s..."
            if delay >= max_delay:
                if waited_max_delay:
                    print(f"{msg} 已达到最大退避，停止重试。")
                    raise
                waited_max_delay = True
            print(msg)
            time.sleep(delay)
            attempt += 1


def _read_json_list(path: str) -> List[str]:
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as pf:
            txt = pf.read()
            if not txt or not txt.strip():
                return []
            return json.loads(txt)
    except Exception:
        return []


def _write_json_list(path: str, lst: Iterable[str]):
    try:
        with open(path, "w", encoding="utf-8") as pf:
            json.dump(list(lst), pf, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        print(f"写入 JSON 文件失败 ({path}): {exc}")


def _read_csv_header(csv_path: str) -> List[str]:
    try:
        if not os.path.exists(csv_path):
            return []
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            first = next(reader, None)
            return first or []
    except Exception:
        return []


def _ensure_fieldnames(csv_path: str, metrics_keys: List[str]) -> List[str]:
    existing = _read_csv_header(csv_path)
    if existing:
        merged = list(dict.fromkeys(existing + metrics_keys))
    else:
        merged = list(metrics_keys)
    return merged


def _write_metrics(csv_path: str, metrics: Dict[str, Any]):
    fieldnames = _ensure_fieldnames(csv_path, list(metrics.keys()))
    write_header = not os.path.exists(csv_path) or not _read_csv_header(csv_path)
    with open(csv_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        # 确保所有字段都有值
        row = {k: metrics.get(k, "") for k in fieldnames}
        writer.writerow(row)


def read_total_processed_from_csv(csv_path: str) -> int:
    """读取 CSV 中记录的最大 end 值。兼容缺列/旧格式。"""
    try:
        if not os.path.exists(csv_path):
            return 0
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            last_end = 0
            for row in reader:
                try:
                    e = int(row.get("end") or 0)
                    if e > last_end:
                        last_end = e
                except Exception:
                    continue
            return last_end
    except Exception:
        return 0


# =====================
# 核心批次逻辑
# =====================
def run_batch(
    cfg: CrawlerConfig,
    batch_idx: int,
    items: List[str],
    request_delay: float,
    search_delay: float,
    jitter_max: float,
    processed_offset_start: int = 0,
    is_last_batch: bool = False,
    graceful_wait_seconds: Optional[float] = None,
):
    """运行单个批次的爬取任务
    
    Args:
        cfg: 爬虫配置对象
        batch_idx: 批次索引
        items: 待处理的项目列表
        request_delay: 请求延迟（秒）
        search_delay: 搜索延迟（秒）
        jitter_max: 最大随机抖动（秒）
        processed_offset_start: 已处理偏移起始值
        is_last_batch: 是否为最后一批
        graceful_wait_seconds: 优雅关闭等待时间（秒）
    """
    graceful_wait_seconds = graceful_wait_seconds or cfg.default_graceful_wait

    # 初始化结构化日志器
    logger = get_logger(f"crawl_runner_{cfg.name}")
    
    start_time = time.perf_counter()
    processed = 0
    success = 0
    fail = 0
    errors: List[Any] = []
    missing_detail_pages = 0
    was_interrupted = False
    termination_reason = "batch_completed"
    
    # 记录批次开始
    logger.crawl_start(cfg.name, len(items), extra_data={
        'batch_idx': batch_idx,
        'request_delay': request_delay,
        'search_delay': search_delay
    })

    pending_path = cfg.pending_path()
    pending_list = _read_json_list(pending_path)
    pending_set = set(pending_list)

    q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    writer_stop = threading.Event()
    writer_stats = {"success": 0, "fail": 0}
    lock = threading.Lock()

    def _call_with_network_retry(func: Callable, *args, **kwargs):
        """包装函数，遇到网络异常时等待后重试，超过限制则抛出 NetworkOutageError。"""

        def action():
            try:
                return func(*args, **kwargs)
            except requests.RequestException as exc:
                # 使用新的异常系统
                logger.error("网络请求异常", extra_data={
                    'exception_type': type(exc).__name__,
                    'exception_message': str(exc)
                })
                raise TransientAccessError(str(exc)) from exc
            except Exception as exc:
                # 捕获其他异常并记录
                logger.error("未知异常", extra_data={
                    'exception_type': type(exc).__name__,
                    'exception_message': str(exc)
                })
                raise

        try:
            return _retry_with_backoff(
                action,
                "网络异常",
                base=cfg.retry_backoff_base,
                max_delay=cfg.retry_backoff_max,
            )
        except TransientAccessError as exc:
            logger.error("网络重试失败", extra_data={
                'error_detail': exc.detail,
                'retry_attempts': 'max_reached'
            })
            print("网络异常持续存在，已达到最大退避时长，终止本批次。")
            raise NetworkOutageError from exc

    def persist_pending(label: str):
        """持久化待处理项目到文件"""
        try:
            with lock:
                lst = _read_json_list(pending_path)
                if label not in lst:
                    lst.append(label)
                    _write_json_list(pending_path, lst)
                    logger.debug("已添加到待处理列表", extra_data={'label': label})
        except Exception as exc:  # noqa: BLE001
            logger.error("写入 pending 文件失败", extra_data={
                'exception_type': type(exc).__name__,
                'exception_message': str(exc),
                'label': label
            })

    def db_writer():
        """数据库写入线程函数"""
        buffer: List[Dict[str, Any]] = []
        last_flush = time.time()
        logger.debug("数据库写入线程启动")
        
        while not writer_stop.is_set() or not q.empty():
            try:
                item = q.get(timeout=0.5)
            except queue.Empty:
                item = None

            if item is not None:
                buffer.append(item)

            should_flush = (
                (len(buffer) >= cfg.db_batch_size)
                or (buffer and (time.time() - last_flush) > cfg.db_flush_interval)
                or (writer_stop.is_set() and buffer)
            )
            if not should_flush:
                continue

            logger.debug("开始批量写入数据库", extra_data={'batch_size': len(buffer)})
            for it in buffer:
                try:
                    ok = cfg.save_func(it)
                    if ok:
                        writer_stats["success"] += 1
                        label_val = it.get("data", {}).get(cfg.label_key)
                        if label_val:
                            try:
                                with lock:
                                    lst = _read_json_list(pending_path)
                                    if label_val in lst:
                                        lst.remove(label_val)
                                        _write_json_list(pending_path, lst)
                                        logger.debug("从待处理列表移除", extra_data={'label': label_val})
                            except Exception as exc:  # noqa: BLE001
                                logger.error("更新 pending 失败", extra_data={
                                    'exception_type': type(exc).__name__,
                                    'exception_message': str(exc),
                                    'label': label_val
                                })
                        # 记录数据库操作成功
                        logger.db_operation('insert', cfg.name, it.get('id'), True)
                    else:
                        writer_stats["fail"] += 1
                        logger.db_operation('insert', cfg.name, it.get('id'), False, 
                                           extra_data={'reason': 'save_func_returned_false'})
                except Exception as exc:  # noqa: BLE001
                    writer_stats["fail"] += 1
                    logger.error("DB 写入异常", extra_data={
                        'exception_type': type(exc).__name__,
                        'exception_message': str(exc),
                        'item_id': it.get('id')
                    })
                    # 使用新的异常系统
                    if "connection" in str(exc).lower():
                        raise DatabaseException("数据库连接失败", operation="insert", table=cfg.name) from exc
            buffer = []
            last_flush = time.time()
        
        logger.debug("数据库写入线程结束")

    writer = threading.Thread(target=db_writer, daemon=True)
    writer.start()

    session = requests.Session()
    chunk_processed = 0

    def _process_item(item: str):
        """处理单个项目的爬取逻辑"""
        nonlocal processed, success, fail, was_interrupted, missing_detail_pages, termination_reason

        def mark_processed():
            nonlocal processed
            processed += 1

        def _resolve_search_url():
            """解析搜索URL"""
            try:
                url = _call_with_network_retry(cfg.search_func, item, search_delay, session)
                if isinstance(url, dict) and url.get("blocked"):
                    raise TransientAccessError(f"status={url.get('blocked')}")
                return url
            except Exception as exc:
                logger.crawl_error(cfg.name, f"search:{item}", "search_failed", extra_data={
                    'exception_type': type(exc).__name__,
                    'exception_message': str(exc)
                })
                raise

        def _fetch_detail(url):
            """获取详情页数据"""
            try:
                # 确保传递给detail_func的是字符串
                url_str = url if isinstance(url, str) else str(url)
                data = _call_with_network_retry(cfg.detail_func, url_str, request_delay, session)
                if isinstance(data, dict) and (
                    data.get("error") in ("blocked",)
                    or (data.get("status") in (429, 403, 503))
                ):
                    blocked_status = data.get("status")
                    if not blocked_status and data.get("error") == "blocked":
                        blocked_status = "blocked"
                    raise TransientAccessError(f"status={blocked_status}")
                return data
            except Exception as exc:
                logger.crawl_error(cfg.name, url, "detail_fetch_failed", extra_data={
                    'exception_type': type(exc).__name__,
                    'exception_message': str(exc)
                })
                raise

        try:
            time.sleep(random.uniform(0, jitter_max))
            url = _retry_with_backoff(
                _resolve_search_url,
                "限流/封禁 (搜索)",
                base=cfg.retry_backoff_base,
                max_delay=cfg.retry_backoff_max,
            )
            if isinstance(url, dict) and url.get("error"):
                fail += 1
                errors.append((item, url.get("error")))
                logger.crawl_error(cfg.name, f"search:{item}", "search_error", extra_data={
                    'error': url.get("error")
                })
                mark_processed()
                return True

            if url is None:
                missing_detail_pages += 1
                logger.warning("未找到详情页", extra_data={
                    'item': item,
                    'data_type': cfg.name
                })
                mark_processed()
                return True

            time.sleep(random.uniform(0, jitter_max))
            data = _retry_with_backoff(
                lambda: _fetch_detail(url),
                "限流/封禁 (详情页)",
                base=cfg.retry_backoff_base,
                max_delay=cfg.retry_backoff_max,
            )
            if isinstance(data, dict) and "error" in data:
                fail += 1
                errors.append((item, data.get("error")))
                logger.crawl_error(cfg.name, url, "detail_error", extra_data={
                    'error': data.get("error"),
                    'item': item
                })
                mark_processed()
                return True

            if not isinstance(data, dict):
                logger.warning("数据格式异常，使用默认格式", extra_data={
                    'url': url,
                    'item': item,
                    'data_type': type(data).__name__
                })
                data = {"url": url, "data": {cfg.label_key: item}}
            else:
                # 确保数据中包含标签
                if "data" not in data or not data.get("data"):
                    data = {"url": url, "data": {cfg.label_key: item}}
                else:
                    data.setdefault("data", {})
                    if not data["data"].get(cfg.label_key):
                        data["data"][cfg.label_key] = item
                        logger.debug("添加缺失的标签", extra_data={
                            'label': item,
                            'label_key': cfg.label_key
                        })

            label_value = data.get("data", {}).get(cfg.label_key) or item
            persist_pending(label_value)
            pending_set.add(label_value)
            q.put(data)
            success += 1
            logger.debug("项目处理成功", extra_data={
                'item': item,
                'label_value': label_value,
                'url': url
            })
            mark_processed()
            return True
        except KeyboardInterrupt:
            termination_reason = "manual_exit"
            logger.warning("收到中断信号，等待写库后退出", extra_data={
                'graceful_wait_seconds': graceful_wait_seconds
            })
            writer_stop.set()
            try:
                writer.join(timeout=graceful_wait_seconds)
            except Exception as exc:
                logger.error("等待写入线程结束失败", extra_data={
                    'exception_type': type(exc).__name__,
                    'exception_message': str(exc)
                })
            was_interrupted = True
            return False
        except NetworkOutageError:
            logger.error("网络中断，停止批次处理")
            raise
        except Exception as exc:  # noqa: BLE001
            fail += 1
            errors.append((item, str(exc)))
            logger.crawl_error(cfg.name, f"item:{item}", "processing_error", extra_data={
                'exception_type': type(exc).__name__,
                'exception_message': str(exc)
            })
            mark_processed()
            return True

    def _process_pending_items():
        """处理待处理项目列表"""
        logger.info("开始处理待处理项目", extra_data={'pending_count': len(pending_list)})
        for it in pending_list:
            if not _process_item(it):
                return False
        logger.info("待处理项目处理完成")
        return True

    def _process_chunk_items():
        """处理当前批次项目"""
        nonlocal chunk_processed
        logger.info("开始处理批次项目", extra_data={'batch_size': len(items)})
        for it in items:
            if it in pending_set:
                continue
            if not _process_item(it):
                return False
            chunk_processed += 1
        logger.info("批次项目处理完成", extra_data={'processed_count': chunk_processed})
        return True

    pending_completed = False
    try:
        pending_completed = _process_pending_items()
        if pending_completed and not was_interrupted:
            _process_chunk_items()
    except NetworkOutageError:
        logger.error("网络异常仍未恢复，终止本批次以便下次重试")
        was_interrupted = True
        termination_reason = "network_outage"
    finally:
        writer_stop.set()
        writer.join()

    fail += writer_stats.get("fail", 0)

    if termination_reason == "batch_completed":
        if chunk_processed == 0:
            termination_reason = "blocked_ip"
        elif is_last_batch and items and chunk_processed >= len(items):
            termination_reason = "all_done"

    elapsed = time.perf_counter() - start_time
    insert_rate = success / elapsed if elapsed > 0 else 0
    error_rate = fail / processed if processed > 0 else 0

    metrics = {
        "batch_idx": batch_idx,
        "start": processed_offset_start + 1 if chunk_processed > 0 else processed_offset_start,
        "end": processed_offset_start + chunk_processed,
        "processed": processed,
        "success": success,
        "fail": fail,
        "missing_detail_pages": missing_detail_pages,
        "termination_reason": termination_reason,
        "elapsed_seconds": round(elapsed, 3),
        "insert_rate_per_sec": round(insert_rate, 3),
        "error_rate": round(error_rate, 4),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    _write_metrics(cfg.csv_path(), metrics)
    
    # 记录批次完成
    logger.crawl_success(cfg.name, success, fail, extra_data={
        'batch_idx': batch_idx,
        'termination_reason': termination_reason,
        'elapsed_seconds': round(elapsed, 3),
        'insert_rate_per_sec': round(insert_rate, 3)
    })

    if errors:
        err_path = os.path.join(cfg.base_dir, f"batch_{batch_idx}_errors.csv")
        with open(err_path, "w", encoding="utf-8-sig", newline="") as ef:
            ew = csv.writer(ef)
            ew.writerow([cfg.label_key, "error"])
            for e in errors:
                ew.writerow(e)
        logger.warning("已保存错误记录", extra_data={
            'error_file': err_path,
            'error_count': len(errors)
        })

    if was_interrupted:
        logger.warning("批次被中断")
        raise KeyboardInterrupt

    return metrics, chunk_processed


# =====================
# 顶层入口
# =====================
def run_crawl(
    cfg: CrawlerConfig,
    batch_size: Optional[int] = None,
    request_delay: Optional[float] = None,
    search_delay: Optional[float] = None,
    jitter_max: Optional[float] = None,
):
    """运行爬虫主程序
    
    Args:
        cfg: 爬虫配置对象
        batch_size: 批处理大小
        request_delay: 请求延迟（秒）
        search_delay: 搜索延迟（秒）
        jitter_max: 最大随机抖动（秒）
    
    Returns:
        int: 退出码 (0=成功, 1=错误, 2=无数据)
    """
    batch_size = batch_size or cfg.default_batch_size
    request_delay = request_delay if request_delay is not None else cfg.default_request_delay
    search_delay = search_delay if search_delay is not None else cfg.default_search_delay
    jitter_max = jitter_max if jitter_max is not None else cfg.default_jitter_max

    # 初始化日志器
    logger = get_logger(f"crawl_main_{cfg.name}")
    
    items = cfg.get_items()
    if not items:
        logger.error("未获取到数据列表，退出", extra_data={'data_type': cfg.name})
        return 2
    total = len(items)
    logger.info("获取到数据列表", extra_data={
        'data_type': cfg.name,
        'total_count': total,
        'batch_size': batch_size
    })
    print(f"获取到 {total} 个{cfg.name}，分批大小: {batch_size}")

    processed_total = read_total_processed_from_csv(cfg.csv_path())
    if processed_total >= total:
        logger.info("所有数据已处理，跳过爬取", extra_data={
            'data_type': cfg.name,
            'processed_total': processed_total,
            'csv_path': cfg.csv_path()
        })
        print(f"所有{cfg.name}已处理，跳过爬取。性能指标已追加到 {cfg.csv_path()}")
        return 0

    start_index = processed_total
    batch_idx = start_index // batch_size

    while start_index < total:
        current_batch_end = min(((start_index // batch_size) + 1) * batch_size, total)
        if start_index >= current_batch_end:
            break
        chunk = items[start_index:current_batch_end]
        chunk_end = current_batch_end
        
        logger.info("开始处理批次", extra_data={
            'batch_idx': batch_idx,
            'start_index': start_index + 1,
            'end_index': chunk_end,
            'processed_before': start_index,
            'chunk_size': len(chunk)
        })
        
        print(f"开始第 {batch_idx} 批: {start_index+1}-{chunk_end} (已处理 {start_index})")
        try:
            m, chunk_processed = run_batch(
                cfg,
                batch_idx,
                chunk,
                request_delay=request_delay,
                search_delay=search_delay,
                jitter_max=jitter_max,
                processed_offset_start=start_index,
                is_last_batch=(chunk_end >= total),
                graceful_wait_seconds=cfg.default_graceful_wait,
            )
            print("  批次指标:", m)
            
            logger.info("批次完成", extra_data={
                'batch_idx': batch_idx,
                'metrics': m,
                'chunk_processed': chunk_processed
            })
        except KeyboardInterrupt:
            logger.warning("收到中断信号，停止后续批次", extra_data={
                'last_processed_index': start_index
            })
            print("收到中断信号，停止后续批次。下次运行将从上次退出位置继续。")
            return 130

        if chunk_processed == 0:
            logger.warning("本批次未处理新的条目，可能被封或空闲", extra_data={
                'batch_idx': batch_idx,
                'chunk_size': len(chunk)
            })
            print("本批次未处理新的条目，可能被封或空闲，先停止以便下次继续。")
            break

        start_index += chunk_processed
        if chunk_processed < len(chunk):
            logger.warning("本批次未完全完成", extra_data={
                'batch_idx': batch_idx,
                'chunk_processed': chunk_processed,
                'chunk_size': len(chunk)
            })
            print("本批次未完全完成，将在下一次运行继续剩余条目。")
            break

        batch_idx += 1

    if start_index >= total:
        logger.info("全部批次完成", extra_data={
            'total_processed': start_index,
            'csv_path': cfg.csv_path()
        })
        print(f"全部批次完成。性能指标已追加到 {cfg.csv_path()}")
    else:
        logger.info("本次运行结束", extra_data={
            'last_processed_index': start_index,
            'remaining_count': total - start_index
        })
        print("本次运行处理到", start_index, "条，下一次将从此位置继续。")
    return 0


def run_crawl_main(cfg: CrawlerConfig):
    """方便 extract_*.py 作为脚本直接运行。"""
    return run_crawl(cfg)
