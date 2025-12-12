# -*- coding: utf-8 -*-
"""
分批爬取成语并记录每批性能指标（耗时、插入速率、错误率）、可续爬的 pending 清理逻辑及后台批量写入。
默认每批 1000 条，结果会追加写入 ciyu/batch_metrics.csv，并自动按照上次运行的 end 值续爬。
错误记录追加到 chengyu/batch_{batch_idx}_errors.csv，包含成语与错误信息。

注意：这个脚本会实际请求网页并写入数据库（含 pending 回写、限流重试、网络异常重试等机制），
请确认批量操作前已准备好网络与数据库权限。

使用示例：
    python batch_crawl.py
"""
import time
import csv
import os
import queue
import random
import threading
import requests
import json

from extract_ciyu import (
    get_words_from_neo4j,
    get_ciyu_url,
    extract_ciyu_details_from_url,
)
from ciyu_mysql import save_ciyu_to_db

# === 网络异常（断网、封IP、限流等）重试配置 ===
RETRY_BACKOFF_BASE = 300  # 初始退避秒数
RETRY_BACKOFF_MAX = 15  # 最大退避时长
# ==========================================

class NetworkOutageError(Exception):
    """表示网络异常未恢复，需要停止本批次并等待人为重启。

    这个异常类本身没有任何逻辑，只作为标记使用。网路重试的实际行为都在
    `_call_with_network_retry` 内部实现。"""


class TransientAccessError(Exception):
    """用于表示需要退避重试的临时访问失败（断网、封禁等）。"""

    def __init__(self, detail=None):
        super().__init__(detail)
        self.detail = detail

CSV_PATH = os.path.join(os.path.dirname(__file__), 'batch_metrics.csv')

# === 批量爬取的配置 ===
DEFAULT_BATCH_SIZE = 1000  # 批量处理的词语数量
DEFAULT_REQUEST_DELAY = 0.0  # 词语详情请求的固定延迟
DEFAULT_SEARCH_DELAY = 0.0   # 搜索词语 URL 的固定延迟
DEFAULT_JITTER_MAX = 0.8     # 每次请求的最大随机抖动秒数
PENDING_PATH = os.path.join(os.path.dirname(__file__), 'pending.json')
DB_BATCH_SIZE = 50 # 每次写入数据库的批量大小
DB_FLUSH_INTERVAL = 3.0 # 数据库写入缓冲区最大等待秒数
DEFAULT_GRACEFUL_SHUTDOWN_WAIT = 3.0 # Ctrl+C 后等待写库的秒数（可调整）
# ==========================================


def _compute_backoff_delay(attempt):
    try:
        return min(RETRY_BACKOFF_BASE * (2 ** attempt), RETRY_BACKOFF_MAX)
    except OverflowError:
        return RETRY_BACKOFF_MAX


def _retry_with_backoff(action, label):
    attempt = 0
    waited_max_delay = False
    while True:
        try:
            return action()
        except TransientAccessError as exc:
            detail_suffix = f" ({exc.detail})" if exc.detail else ""
            delay = _compute_backoff_delay(attempt)
            msg = f"检测到{label}{detail_suffix}, 第 {attempt+1} 次重试，等待 {delay}s..."
            if delay >= RETRY_BACKOFF_MAX:
                if waited_max_delay:
                    print(f"{msg} 已达到最大退避，停止重试。")
                    raise
                waited_max_delay = True
            print(msg)
            time.sleep(delay)
            attempt += 1


def read_total_processed_from_csv():
    """从 CSV 文件读取已处理的最大 end 值，用于续爬。"""
    try:
        if not os.path.exists(CSV_PATH):
            return 0
        with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            last_end = 0
            for row in reader:
                try:
                    e = int(row.get('end') or 0)
                    if e > last_end:
                        last_end = e
                except Exception:
                    continue
            return last_end
    except Exception:
        return 0


def run_batch(batch_idx, words, request_delay=DEFAULT_REQUEST_DELAY, search_delay=DEFAULT_SEARCH_DELAY,
              jitter_max=DEFAULT_JITTER_MAX, db_batch_size=DB_BATCH_SIZE,
              graceful_wait_seconds=DEFAULT_GRACEFUL_SHUTDOWN_WAIT, processed_offset_start=0,
              is_last_batch=False):
    """单线程抓取 + 后台批量写入（生产者-消费者），支持随机抖动与断点续爬。"""
    start_time = time.perf_counter()
    processed = 0
    success = 0
    fail = 0
    errors = []
    missing_detail_pages = 0
    was_interrupted = False
    termination_reason = 'batch_completed'

    def read_json_list(path):
        try:
            if not os.path.exists(path):
                return []
            with open(path, 'r', encoding='utf-8') as pf:
                txt = pf.read()
                if not txt or not txt.strip():
                    return []
                return json.loads(txt)
        except Exception:
            return []

    def write_json_list(path, lst):
        try:
            with open(path, 'w', encoding='utf-8') as pf:
                json.dump(lst, pf, ensure_ascii=False)
        except Exception as exc:
            print(f'写入 JSON 文件失败 ({path}):', exc)

    pending_list = read_json_list(PENDING_PATH)
    pending_set = set(pending_list)

    q = queue.Queue()
    writer_stop = threading.Event()
    writer_stats = {'success': 0, 'fail': 0}
    lock = threading.Lock()

    def _call_with_network_retry(func, *args, **kwargs):
        """包装函数，遇到网络异常时等待后重试，超过限制则抛出 NetworkOutageError。"""
        def action():
            try:
                return func(*args, **kwargs)
            except requests.RequestException as exc:
                raise TransientAccessError(str(exc)) from exc

        try:
            return _retry_with_backoff(action, '网络异常')
        except TransientAccessError as exc:
            print('网络异常持续存在，已达到最大退避时长，终止本批次。')
            raise NetworkOutageError from exc

    def persist_pending(word):
        try:
            with lock:
                lst = read_json_list(PENDING_PATH)
                if word not in lst:
                    lst.append(word)
                    write_json_list(PENDING_PATH, lst)
        except Exception as exc:
            print('写入 pending 文件失败:', exc)

    def db_writer():
        buffer = []
        last_flush = time.time()
        while not writer_stop.is_set() or not q.empty():
            try:
                item = q.get(timeout=0.5)
            except queue.Empty:
                item = None

            if item is not None:
                buffer.append(item)

            if (len(buffer) >= db_batch_size) or (buffer and (time.time() - last_flush) > DB_FLUSH_INTERVAL) or (writer_stop.is_set() and buffer):
                for it in buffer:
                    try:
                        ok = save_ciyu_to_db(it)
                        if ok:
                            writer_stats['success'] += 1
                            word = None
                            try:
                                word = it.get('data', {}).get('word')
                            except Exception:
                                word = None
                            if word:
                                try:
                                    with lock:
                                        lst = read_json_list(PENDING_PATH)
                                        if word in lst:
                                            lst.remove(word)
                                            write_json_list(PENDING_PATH, lst)
                                except Exception as exc:
                                    print('更新 pending 失败:', exc)
                        else:
                            writer_stats['fail'] += 1
                    except Exception as exc:
                        writer_stats['fail'] += 1
                        print('DB 写入异常:', exc)
                buffer = []
                last_flush = time.time()

    writer = threading.Thread(target=db_writer, daemon=True)
    writer.start()

    chunk_processed = 0

    def _process_word(word):
        nonlocal processed, success, fail, was_interrupted, missing_detail_pages, termination_reason

        def mark_processed():
            nonlocal processed
            processed += 1

        def _resolve_search_url():
            url = _call_with_network_retry(get_ciyu_url, word, delay=search_delay)
            if isinstance(url, dict) and url.get('blocked'):
                raise TransientAccessError(f"status={url.get('blocked')}")
            return url

        def _fetch_detail():
            data = _call_with_network_retry(extract_ciyu_details_from_url, url, delay=request_delay)
            if isinstance(data, dict) and (data.get('error') in ('blocked',) or (data.get('status') in (429, 403, 503))):
                blocked_status = data.get('status')
                if not blocked_status and data.get('error') == 'blocked':
                    blocked_status = 'blocked'
                raise TransientAccessError(f"status={blocked_status}")
            return data

        try:
            time.sleep(random.uniform(0, jitter_max))
            url = _retry_with_backoff(_resolve_search_url, '限流/封禁 (搜索)')
            if isinstance(url, dict) and url.get('error'):
                fail += 1
                errors.append((word, url.get('error')))
                mark_processed()
                return True

            if url is None:
                missing_detail_pages += 1
                mark_processed()
                return True

            time.sleep(random.uniform(0, jitter_max))
            data = _retry_with_backoff(_fetch_detail, '限流/封禁 (详情页)')
            if isinstance(data, dict) and 'error' in data:
                fail += 1
                errors.append((word, data.get('error')))
                mark_processed()
                return True

            if 'data' not in data or not data.get('data'):
                data['data'] = {'word': word}
            else:
                if not data['data'].get('word'):
                    data['data']['word'] = word

            normalized_word = data.get('data', {}).get('word') or word
            persist_pending(normalized_word)
            pending_set.add(normalized_word)
            q.put(data)
            success += 1
            mark_processed()
            return True
        except KeyboardInterrupt:
            termination_reason = 'manual_exit'
            print('收到中断信号，等待短时间写库后退出...')
            writer_stop.set()
            try:
                writer.join(timeout=graceful_wait_seconds)
            except Exception:
                pass
            was_interrupted = True
            return False
        except NetworkOutageError:
            raise
        except Exception as exc:
            fail += 1
            errors.append((word, str(exc)))
            mark_processed()
            return True

    def _process_pending_words():
        for pending in pending_list:
            if not _process_word(pending):
                return False
        return True

    def _process_chunk_words():
        nonlocal chunk_processed
        for word in words:
            if word in pending_set:
                continue
            if not _process_word(word):
                return False
            chunk_processed += 1
        return True

    pending_completed = False # 是否已完成 pending 列表的处理
    try:
        pending_completed = _process_pending_words()
        if pending_completed and not was_interrupted:
            _process_chunk_words()
    except NetworkOutageError:
        print('网络异常仍未恢复，终止本批次以便下次重试。')
        was_interrupted = True
        termination_reason = 'network_outage'
    finally:
        writer_stop.set()
        writer.join()

    fail += writer_stats.get('fail', 0)

    if termination_reason == 'batch_completed':
        if chunk_processed == 0:
            termination_reason = 'blocked_ip'
        elif is_last_batch and words and chunk_processed >= len(words):
            termination_reason = 'all_done'

    elapsed = time.perf_counter() - start_time
    insert_rate = success / elapsed if elapsed > 0 else 0
    error_rate = fail / processed if processed > 0 else 0

    metrics = {
        'batch_idx': batch_idx,
        'start': processed_offset_start + 1 if chunk_processed > 0 else processed_offset_start,
        'end': processed_offset_start + chunk_processed,
        'processed': processed,
        'success': success,
        'fail': fail,
        'missing_detail_pages': missing_detail_pages,
        'termination_reason': termination_reason,
        'elapsed_seconds': round(elapsed, 3),
        'insert_rate_per_sec': round(insert_rate, 3),
        'error_rate': round(error_rate, 4),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(metrics)

    if errors:
        err_path = os.path.join(os.path.dirname(__file__), f'batch_{batch_idx}_errors.csv')
        with open(err_path, 'w', encoding='utf-8-sig', newline='') as ef:
            ew = csv.writer(ef)
            ew.writerow(['word', 'error'])
            for e in errors:
                ew.writerow(e)

    if was_interrupted:
        raise KeyboardInterrupt

    return metrics, chunk_processed


def main(batch_size=100, request_delay=DEFAULT_REQUEST_DELAY, search_delay=DEFAULT_SEARCH_DELAY):
    words = get_words_from_neo4j()
    if not words:
        print('未从 Neo4j 获取到词语列表，退出')
        return 2
    total = len(words)
    print(f'获取到 {total} 个词语，分批大小: {batch_size}')

    processed_total = read_total_processed_from_csv()
    if processed_total >= total:
        print('所有词语已处理，跳过爬取。性能指标已追加到', CSV_PATH)
        return 0

    start_index = processed_total
    batch_idx = start_index // batch_size

    while start_index < total:
        current_batch_end = min(((start_index // batch_size) + 1) * batch_size, total)
        if start_index >= current_batch_end:
            break
        chunk = words[start_index:current_batch_end]
        chunk_end = current_batch_end
        print(f'开始第 {batch_idx} 批: {start_index+1}-{chunk_end} (已处理 {start_index})')
        try:
            m, chunk_processed = run_batch(batch_idx, chunk, request_delay=request_delay,
                                            search_delay=search_delay,
                                            processed_offset_start=start_index,
                                            is_last_batch=(chunk_end >= total))
            print('  批次指标:', m)
        except KeyboardInterrupt:
            print('收到中断信号，停止后续批次。下次运行将从上次退出位置继续。')
            return 130

        if chunk_processed == 0:
            print('本批次未处理新的词语，可能被封或空闲，先停止以便下次继续。')
            break

        start_index += chunk_processed
        if chunk_processed < len(chunk):
            print('本批次未完全完成，将在下一次运行继续剩余词语。')
            break

        batch_idx += 1

    if start_index >= total:
        print('全部批次完成。性能指标已追加到', CSV_PATH)
    else:
        print('本次运行处理到', start_index, '条词语，下一次将从此位置继续。')
    return 0


if __name__ == '__main__':
    # 直接使用文件顶部的默认常量，运行前可手动修改
    exit(main(batch_size=DEFAULT_BATCH_SIZE,
              request_delay=DEFAULT_REQUEST_DELAY,
              search_delay=DEFAULT_SEARCH_DELAY))
