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
from chengyu_neo4j import get_idioms_from_neo4j
from extract_chengyu import get_chengyu_url, extract_chengyu_details_from_url, save_chengyu_to_db

CSV_PATH = os.path.join(os.path.dirname(__file__), 'batch_metrics.csv')

# === 批量爬取的配置 ===
DEFAULT_BATCH_SIZE = 1000 # 批量处理的成语数量
DEFAULT_REQUEST_DELAY = 1.0 # 每个成语详情请求的延迟
DEFAULT_SEARCH_DELAY = 0.5  # 搜索成语 URL 时的延迟
# ==========================================


def run_batch(batch_idx, idioms, request_delay=1.0, search_delay=0.5):
    start_time = time.perf_counter()
    processed = 0
    success = 0
    fail = 0
    errors = []

    for chengyu in idioms:
        processed += 1
        try:
            url = get_chengyu_url(chengyu, delay=search_delay)
            if not url:
                fail += 1
                errors.append((chengyu, 'no_url'))
                continue
            data = extract_chengyu_details_from_url(url, delay=request_delay)
            ok = save_chengyu_to_db(data)
            if ok:
                success += 1
            else:
                fail += 1
                errors.append((chengyu, 'save_failed'))
        except Exception as e:
            fail += 1
            errors.append((chengyu, str(e)))

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
        m = run_batch(batch_idx, chunk, request_delay=request_delay, search_delay=search_delay)
        print('  批次指标:', m)
        batch_idx += 1

    print('全部批次完成。性能指标已追加到', CSV_PATH)
    return 0


if __name__ == '__main__':
    # 直接使用文件顶部的默认常量，便于运行前手动修改
    exit(main(batch_size=DEFAULT_BATCH_SIZE,
              request_delay=DEFAULT_REQUEST_DELAY,
              search_delay=DEFAULT_SEARCH_DELAY))
