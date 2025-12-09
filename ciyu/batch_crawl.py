# -*- coding: utf-8 -*-
"""
分批爬取词语并记录每批性能指标（耗时、插入速率、错误率）。
结果会追加写入 ciyu/batch_metrics.csv。

使用：在文件顶部修改 DEFAULT_* 常量后直接运行
    python batch_crawl.py
"""
import time
import csv
import os

from extract_ciyu import (
    get_words_from_neo4j,
    get_ciyu_url,
    extract_ciyu_details_from_url,
)
from ciyu_mysql import save_ciyu_to_db

CSV_PATH = os.path.join(os.path.dirname(__file__), 'batch_metrics.csv')

# === 配置（直接在这里修改） ===
DEFAULT_BATCH_SIZE = 1000
DEFAULT_REQUEST_DELAY = 1.0
DEFAULT_SEARCH_DELAY = 0.5
# ==============================


def run_batch(batch_idx, words, request_delay=1.0, search_delay=0.5):
    start_time = time.perf_counter()
    processed = 0
    success = 0
    fail = 0
    errors = []

    for w in words:
        processed += 1
        try:
            url = get_ciyu_url(w, delay=search_delay)
            if not url:
                fail += 1
                errors.append((w, 'no_url'))
                continue
            data = extract_ciyu_details_from_url(url, delay=request_delay)
            ok = save_ciyu_to_db(data)
            if ok:
                success += 1
            else:
                fail += 1
                errors.append((w, 'save_failed'))
        except Exception as e:
            fail += 1
            errors.append((w, str(e)))

    elapsed = time.perf_counter() - start_time
    insert_rate = success / elapsed if elapsed > 0 else 0
    error_rate = fail / processed if processed > 0 else 0

    metrics = {
        'batch_idx': batch_idx,
        'start': batch_idx * len(words) + 1,
        'end': batch_idx * len(words) + len(words),
        'processed': processed,
        'success': success,
        'fail': fail,
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

    return metrics


def chunked(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i:i+n]


def main(batch_size=100, request_delay=1.0, search_delay=0.5):
    words = get_words_from_neo4j()
    if not words:
        print('未从 Neo4j 获取到词语列表，退出')
        return 2
    total = len(words)
    print(f'获取到 {total} 个词语，分批大小: {batch_size}')

    batch_idx = 0
    for chunk in chunked(words, batch_size):
        print(f'开始第 {batch_idx} 批: {batch_idx*batch_size+1}-{min((batch_idx+1)*batch_size, total)}')
        m = run_batch(batch_idx, chunk, request_delay=request_delay, search_delay=search_delay)
        print('  批次指标:', m)
        batch_idx += 1

    print('全部批次完成。性能指标已追加到', CSV_PATH)
    return 0


if __name__ == '__main__':
    exit(main(batch_size=DEFAULT_BATCH_SIZE,
              request_delay=DEFAULT_REQUEST_DELAY,
              search_delay=DEFAULT_SEARCH_DELAY))
