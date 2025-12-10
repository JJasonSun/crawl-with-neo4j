# -*- coding: utf-8 -*-
"""
分批爬取成语并记录每批性能指标（耗时、插入速率、错误率）。
默认每批 100 条。结果会追加写入 chengyu/batch_metrics.csv。

注意：这个脚本会实际请求网页并写入数据库，请确保你想现在执行完整爬取。

使用示例：
    python batch_crawl.py --batch 100 --request-delay 1.0 --search-delay 0.5
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

CSV_PATH = os.path.join(os.path.dirname(__file__), 'batch_metrics.csv')

# === 批量爬取的配置 ===
DEFAULT_BATCH_SIZE = 1000 # 批量处理的成语数量
DEFAULT_REQUEST_DELAY = 0.0 # 每个成语详情请求的延迟（由抖动控制）
DEFAULT_SEARCH_DELAY = 0.0  # 搜索成语 URL 时的延时（由抖动控制）
DEFAULT_JITTER_MAX = 0.8    # 每次请求的最大随机抖动（秒）
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), 'processed.json')
PENDING_PATH = os.path.join(os.path.dirname(__file__), 'pending.json')
DB_BATCH_SIZE = 50
DB_FLUSH_INTERVAL = 3.0
MAX_BLOCK_RETRIES = 1        # 当检测到被封时的最大重试次数（0 表示不重试，直接停止）
BLOCK_BACKOFF_BASE = 60     # 初始退避秒数
BLOCK_BACKOFF_MAX = 3600    # 最大退避时长
DEFAULT_GRACEFUL_SHUTDOWN_WAIT = 3.0  # Ctrl+C 后等待写库的最长秒数（可调整）
# ==========================================


def run_batch(batch_idx, idioms, request_delay=0.0, search_delay=0.0, jitter_max=DEFAULT_JITTER_MAX, db_batch_size=DB_BATCH_SIZE, graceful_wait_seconds=DEFAULT_GRACEFUL_SHUTDOWN_WAIT):
    """单线程抓取 + 后台批量写入（生产者-消费者），支持随机抖动与断点续爬。
    """
    start_time = time.perf_counter()
    processed = 0
    success = 0
    fail = 0
    errors = []

    # helper to safely read/write json lists (handles empty/corrupt files)
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

    # load processed set for checkpoint resume
    processed_set = set(read_json_list(PROCESSED_PATH))
    # load pending set (items that were queued previously but not yet confirmed written)
    pending_list = read_json_list(PENDING_PATH)
    pending_set = set(pending_list)

    q = queue.Queue()
    writer_stop = threading.Event()
    writer_stats = {'success': 0, 'fail': 0}
    lock = threading.Lock()

    def persist_processed(ch):
        # append to processed file (keep it small)
        try:
            with lock:
                lst = read_json_list(PROCESSED_PATH)
                if ch not in lst:
                    lst.append(ch)
                    write_json_list(PROCESSED_PATH, lst)
        except Exception as e:
            print('写入 processed 文件失败:', e)

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

            # flush conditions
            if (len(buffer) >= db_batch_size) or (buffer and (time.time() - last_flush) > DB_FLUSH_INTERVAL) or (writer_stop.is_set() and buffer):
                # write buffer
                for it in buffer:
                    try:
                        ok = save_chengyu_to_db(it)
                        if ok:
                            writer_stats['success'] += 1
                            # mark as processed (use chengyu name from parsed data if available)
                            chn = None
                            try:
                                chn = it.get('data', {}).get('chengyu')
                            except Exception:
                                chn = None
                            if chn:
                                # remove from pending and add to processed
                                try:
                                    with lock:
                                        p_lst = read_json_list(PENDING_PATH)
                                        if chn in p_lst:
                                            p_lst.remove(chn)
                                            write_json_list(PENDING_PATH, p_lst)
                                        lst = read_json_list(PROCESSED_PATH)
                                        if chn not in lst:
                                            lst.append(chn)
                                            write_json_list(PROCESSED_PATH, lst)
                                except Exception as e:
                                    print('更新 pending/processed 失败:', e)
                        else:
                            writer_stats['fail'] += 1
                    except Exception as e:
                        writer_stats['fail'] += 1
                        print('DB 写入异常:', e)
                buffer = []
                last_flush = time.time()

        # writer exiting

    writer = threading.Thread(target=db_writer, daemon=True)
    writer.start()

    session = requests.Session()

    # Build working list: first re-process any pending items (they may not have been written),
    # then process remaining idioms that are neither processed nor pending.
    work_list = []
    for p in pending_list:
        if p not in processed_set:
            work_list.append(p)
    for chengyu in idioms:
        if chengyu in processed_set or chengyu in pending_set:
            continue
        work_list.append(chengyu)

    for chengyu in work_list:
        # skip already processed (断点续爬)
        if chengyu in processed_set:
            processed += 1
            continue

        processed += 1
        try:
            # small random jitter before search
            time.sleep(random.uniform(0, jitter_max))
            url = get_chengyu_url(chengyu, delay=search_delay, session=session)

            # If no detail page was found for this chengyu, treat it as processed
            # (persist to processed.json) but do NOT log it as an error in CSV.
            if url is None:
                try:
                    persist_processed(chengyu)
                    processed_set.add(chengyu)
                except Exception:
                    pass
                # count as processed but not a DB insert / not an error
                continue

            # detect blocked response from get_chengyu_url
            blocked_detected = False
            if isinstance(url, dict):
                # structured response: {'blocked': code} or {'error': ...}
                if url.get('blocked'):
                    blocked_detected = True
                elif url.get('error'):
                    fail += 1
                    errors.append((chengyu, url.get('error')))
                    continue

            if blocked_detected:
                # exponential backoff / or immediate stop depending on MAX_BLOCK_RETRIES
                backoff = BLOCK_BACKOFF_BASE
                tried = 0
                recovered = False
                while tried < MAX_BLOCK_RETRIES:
                    print(f"检测到可能的限流/封禁 (status={url.get('blocked')}), 第 {tried+1} 次重试，等待 {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, BLOCK_BACKOFF_MAX)
                    tried += 1
                    url = get_chengyu_url(chengyu, delay=search_delay, session=session)
                    if not isinstance(url, dict) or (isinstance(url, dict) and not url.get('blocked')):
                        recovered = True
                        break

                if not recovered:
                    print(f"检测到被限流/封禁（成语: {chengyu}），已停止本批次爬取以等待人工或下次重试。")
                    # break main loop to allow graceful shutdown and resume later
                    break

            time.sleep(random.uniform(0, jitter_max))
            data = extract_chengyu_details_from_url(url, delay=request_delay, session=session)

            # detect blocked response from extract function
            if isinstance(data, dict) and data.get('error') in ('blocked',) or (isinstance(data, dict) and data.get('status') in (429,403,503)):
                # similar handling as above
                blocked_status = data.get('status') or (data.get('error') == 'blocked' and None)
                backoff = BLOCK_BACKOFF_BASE
                tried = 0
                recovered = False
                while tried < MAX_BLOCK_RETRIES:
                    print(f"检测到可能的限流/封禁 (status={blocked_status}), 第 {tried+1} 次重试，等待 {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, BLOCK_BACKOFF_MAX)
                    tried += 1
                    data = extract_chengyu_details_from_url(url, delay=request_delay, session=session)
                    if not (isinstance(data, dict) and data.get('error') in ('blocked',) or (isinstance(data, dict) and data.get('status') in (429,403,503))):
                        recovered = True
                        break

                if not recovered:
                    print(f"检测到被限流/封禁（详情页: {url}），已停止本批次爬取以等待人工或下次重试。")
                    break

            # if parsing returned error, record and continue
            if isinstance(data, dict) and 'error' in data:
                fail += 1
                errors.append((chengyu, data.get('error')))
                continue

            # attach chengyu name if missing
            try:
                if 'data' not in data or not data.get('data'):
                    data = {'url': url, 'data': {'chengyu': chengyu}}
                else:
                    if not data['data'].get('chengyu'):
                        data['data']['chengyu'] = chengyu
            except Exception:
                pass

            # enqueue for DB writer
            # persist pending immediately to avoid re-queue on abrupt stop
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

        except KeyboardInterrupt:
            # User requested interrupt (Ctrl+C). Signal writer to stop and
            # wait a short configurable time for it to flush queued items.
            print('收到中断信号，等待短时间写库后退出...')
            writer_stop.set()
            try:
                # wait up to graceful_wait_seconds for writer to finish
                writer.join(timeout=graceful_wait_seconds)
            except Exception:
                pass
            # re-raise so caller (main) will stop starting new batches
            raise
        except Exception as e:
            fail += 1
            errors.append((chengyu, str(e)))

    # all tasks queued or loop interrupted
    # signal writer to finish
    writer_stop.set()
    writer.join()

    # collect writer stats
    success += writer_stats.get('success', 0)
    fail += writer_stats.get('fail', 0)

    elapsed = time.perf_counter() - start_time
    insert_rate = success / elapsed if elapsed > 0 else 0
    error_rate = fail / processed if processed > 0 else 0

    metrics = {
        'batch_idx': batch_idx,
        'start': batch_idx * len(idioms) + 1,
        'end': batch_idx * len(idioms) + len(idioms),
        'processed': processed,
        'success': success,
        'fail': fail,
        'elapsed_seconds': round(elapsed, 3),
        'insert_rate_per_sec': round(insert_rate, 3),
        'error_rate': round(error_rate, 4),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    # append metrics to CSV
    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(metrics)

    # also write batch error details file if there are errors
    if errors:
        err_path = os.path.join(os.path.dirname(__file__), f'batch_{batch_idx}_errors.csv')
        with open(err_path, 'w', encoding='utf-8-sig', newline='') as ef:
            ew = csv.writer(ef)
            ew.writerow(['chengyu', 'error'])
            for e in errors:
                ew.writerow(e)

    return metrics


def chunked(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i:i+n]


def main(batch_size=100, request_delay=1.0, search_delay=0.5):
    idioms = get_idioms_from_neo4j()
    if not idioms:
        print('未从 Neo4j 获取到成语列表，退出')
        return 2
    total = len(idioms)
    print(f'获取到 {total} 个成语，分批大小: {batch_size}')

    batch_idx = 0
    for chunk in chunked(idioms, batch_size):
        print(f'开始第 {batch_idx} 批: {batch_idx*batch_size+1}-{min((batch_idx+1)*batch_size, total)}')
        try:
            m = run_batch(batch_idx, chunk, request_delay=request_delay, search_delay=search_delay)
            print('  批次指标:', m)
            batch_idx += 1
        except KeyboardInterrupt:
            print('收到中断信号，停止后续批次。下次运行将从上次退出位置继续。')
            return 130

    print('全部批次完成。性能指标已追加到', CSV_PATH)
    return 0


if __name__ == '__main__':
    # 直接使用文件顶部的默认常量，便于运行前手动修改
    exit(main(batch_size=DEFAULT_BATCH_SIZE,
              request_delay=DEFAULT_REQUEST_DELAY,
              search_delay=DEFAULT_SEARCH_DELAY))
