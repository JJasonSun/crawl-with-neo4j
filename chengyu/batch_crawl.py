# -*- coding: utf-8 -*-
"""
分批爬取成语并记录每批性能指标（耗时、插入速率、错误率）、可续爬的 pending 清理逻辑及批量写入。
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
import requests
import threading
import queue
import random
import json
from chengyu_neo4j import get_idioms_from_neo4j
from extract_chengyu import get_chengyu_url, extract_chengyu_details_from_url
from chengyu_mysql import save_chengyu_to_db

# === 网络异常（断网、封IP、限流等）重试配置 ===
RETRY_BACKOFF_BASE = 300  # 初始退避秒数
RETRY_BACKOFF_MAX = 3600  # 最大退避时长
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
DEFAULT_BATCH_SIZE = 1000 # 批量处理的成语数量
DEFAULT_REQUEST_DELAY = 0.0 # 每个成语详情请求的延迟（由抖动控制）
DEFAULT_SEARCH_DELAY = 0.0  # 搜索成语 URL 时的延时（由抖动控制）
DEFAULT_JITTER_MAX = 0.8    # 每次请求的最大随机抖动（秒）
PENDING_PATH = os.path.join(os.path.dirname(__file__), 'pending.json')
DB_BATCH_SIZE = 50 # 每次写入数据库的批量大小
DB_FLUSH_INTERVAL = 3.0 # 数据库写入缓冲区最大等待秒数
DEFAULT_GRACEFUL_SHUTDOWN_WAIT = 3.0  # Ctrl+C 后等待写库的最长秒数（可调整）
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
    """读取 batch_metrics.csv 中记录的最大已处理数量（end 字段）。"""
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


def run_batch(batch_idx, idioms, request_delay=0.0, search_delay=0.0, jitter_max=DEFAULT_JITTER_MAX,
              db_batch_size=DB_BATCH_SIZE, graceful_wait_seconds=DEFAULT_GRACEFUL_SHUTDOWN_WAIT,
              processed_offset_start=0):
    """单线程抓取 + 后台批量写入（生产者-消费者），支持随机抖动与断点续爬。"""
    start_time = time.perf_counter()
    processed = 0
    success = 0
    fail = 0
    errors = []
    was_interrupted = False

    # 安全读写 JSON 列表（兼容空或损坏的文件）
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
        except Exception as e:
            print(f'写入 JSON 文件失败 ({path}):', e)

    # 读取 pending 列表（尚未确认写入的数据）
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

    def persist_pending(ch):
        try:
            with lock:
                p_lst = read_json_list(PENDING_PATH)
                if ch not in p_lst:
                    p_lst.append(ch)
                    write_json_list(PENDING_PATH, p_lst)
        except Exception as e:
            print('写入 pending 文件失败:', e)

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

            # 刷新条件
            if (len(buffer) >= db_batch_size) or (buffer and (time.time() - last_flush) > DB_FLUSH_INTERVAL) or (writer_stop.is_set() and buffer):
                # 写入缓冲区
                for it in buffer:
                    try:
                        ok = save_chengyu_to_db(it)
                        if ok:
                            writer_stats['success'] += 1
                            chn = None
                            try:
                                chn = it.get('data', {}).get('chengyu')
                            except Exception:
                                chn = None
                            if chn:
                                try:
                                    with lock:
                                        p_lst = read_json_list(PENDING_PATH)
                                        if chn in p_lst:
                                            p_lst.remove(chn)
                                            write_json_list(PENDING_PATH, p_lst)
                                except Exception as e:
                                    print('更新 pending 失败:', e)
                        else:
                            writer_stats['fail'] += 1
                    except Exception as e:
                        writer_stats['fail'] += 1
                        print('DB 写入异常:', e)
                buffer = []
                last_flush = time.time()

        # 写入线程即将退出

    writer = threading.Thread(target=db_writer, daemon=True)
    writer.start()

    session = requests.Session()

    chunk_processed = 0
    missing_detail_pages = 0

    def _process_idiom(chengyu):
        nonlocal processed, success, fail, was_interrupted, missing_detail_pages

        def mark_processed():
            nonlocal processed
            processed += 1

        def _resolve_search_url():
            url = _call_with_network_retry(get_chengyu_url, chengyu, delay=search_delay, session=session)
            if isinstance(url, dict) and url.get('blocked'):
                raise TransientAccessError(f"status={url.get('blocked')}")
            return url

        def _fetch_detail():
            data = _call_with_network_retry(extract_chengyu_details_from_url, url, delay=request_delay, session=session)
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
                errors.append((chengyu, url.get('error')))
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
                errors.append((chengyu, data.get('error')))
                mark_processed()
                return True

            try:
                if 'data' not in data or not data.get('data'):
                    data = {'url': url, 'data': {'chengyu': chengyu}}
                else:
                    if not data['data'].get('chengyu'):
                        data['data']['chengyu'] = chengyu
            except Exception:
                pass

            chn = None
            try:
                chn = data.get('data', {}).get('chengyu')
            except Exception:
                chn = None
            if chn:
                persist_pending(chn)
                pending_set.add(chn)
            q.put(data)
            success += 1
            mark_processed()
            return True
        except KeyboardInterrupt:
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
            errors.append((chengyu, str(exc)))
            mark_processed()
            return True

    def _process_pending_idioms():
        for chengyu in pending_list:
            if not _process_idiom(chengyu):
                return False
        return True

    def _process_chunk_idioms():
        nonlocal chunk_processed
        for chengyu in idioms:
            if chengyu in pending_set:
                continue
            if not _process_idiom(chengyu):
                return False
            chunk_processed += 1
        return True
    
    pending_completed = False # 是否已完成 pending 列表的处理
    try:
        pending_completed = _process_pending_idioms()
        if pending_completed and not was_interrupted:
            _process_chunk_idioms()
    except NetworkOutageError:
        print('网络异常仍未恢复，终止本批次以便下次重试。')
        was_interrupted = True
    finally: # 最后确保写入线程退出
        writer_stop.set()
        writer.join()

    fail += writer_stats.get('fail', 0)

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
            ew.writerow(['chengyu', 'error'])
            for e in errors:
                ew.writerow(e)

    if was_interrupted:
        raise KeyboardInterrupt

    return metrics, chunk_processed


def main(batch_size=100, request_delay=1.0, search_delay=0.5):
    idioms = get_idioms_from_neo4j()
    if not idioms:
        print('未从 Neo4j 获取到成语列表，退出')
        return 2
    total = len(idioms)
    print(f'获取到 {total} 个成语，分批大小: {batch_size}')

    processed_total = read_total_processed_from_csv()
    if processed_total >= total:
        print('所有成语已处理，跳过爬取。性能指标已追加到', CSV_PATH)
        return 0

    start_index = processed_total
    batch_idx = start_index // batch_size

    while start_index < total:
        current_batch_end = min(((start_index // batch_size) + 1) * batch_size, total)
        if start_index >= current_batch_end:
            break
        chunk = idioms[start_index:current_batch_end]
        chunk_end = current_batch_end
        print(f'开始第 {batch_idx} 批: {start_index+1}-{chunk_end} (已处理 {start_index})')
        try:
            m, chunk_processed = run_batch(batch_idx, chunk, request_delay=request_delay,
                                            search_delay=search_delay,
                                            processed_offset_start=start_index)
            print('  批次指标:', m)
        except KeyboardInterrupt:
            print('收到中断信号，停止后续批次。下次运行将从上次退出位置继续。')
            return 130

        if chunk_processed == 0:
            print('本批次未处理新的成语，可能被封或空闲，先停止以便下次继续。')
            break

        start_index += chunk_processed
        if chunk_processed < len(chunk):
            print('本批次未完全完成，将在下一次运行继续剩余成语。')
            break

        batch_idx += 1

    if start_index >= total:
        print('全部批次完成。性能指标已追加到', CSV_PATH)
    else:
        print('本次运行处理到', start_index, '条成语，下一次将从此位置继续。')
    return 0


if __name__ == '__main__':
    # 直接使用文件顶部的默认常量，运行前可手动修改
    exit(main(batch_size=DEFAULT_BATCH_SIZE,
              request_delay=DEFAULT_REQUEST_DELAY,
              search_delay=DEFAULT_SEARCH_DELAY))
