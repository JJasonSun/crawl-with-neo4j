# -*- coding: utf-8 -*-
"""
本地测试脚本：批量爬取若干成语的详情页并打印结果。
使用示例：
    python localtest_chengyu.py
"""

import json
import os
import random
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_chengyu import (
    extract_chengyu_details_from_url,
    get_chengyu_url,
)
from chengyu_neo4j import get_idioms_from_neo4j

COMMON_CHENGYU = [
    "一心一意",
    "三心二意",
    "守株待兔",
    "画蛇添足",
    "亡羊补牢",
]
NEO4J_LIMIT = 45


def print_chengyu_data(chengyu_data: dict) -> None:
    if "error" in chengyu_data:
        print(f"❌ 爬取失败: {chengyu_data['error']}")
        return

    data = chengyu_data.get("data", {})
    print(f"成语: {data.get('chengyu', 'N/A')}")
    print(f"拼音: {data.get('pinyin', 'N/A')}")
    print(f"注音: {data.get('zhuyin', 'N/A')}")
    print(f"感情色彩: {data.get('emotion', 'N/A')}")
    print(f"英文翻译: {data.get('translation', 'N/A')}")

    print("\n近义词:")
    synonyms = data.get("synonyms", [])
    if synonyms:
        for idx, synonym in enumerate(synonyms, start=1):
            print(f"  {idx}. {synonym}")
    else:
        print("  无")

    print("\n反义词:")
    antonyms = data.get("antonyms", [])
    if antonyms:
        for idx, antonym in enumerate(antonyms, start=1):
            print(f"  {idx}. {antonym}")
    else:
        print("  无")


def collect_candidates(limit: int) -> list[str]:
    """返回 5 个硬编码成语加上从 Neo4j 拉取的候选，按实际数量拼接。"""
    candidates = COMMON_CHENGYU.copy()
    seen = set(candidates)

    try:
        neo4j_idioms = get_idioms_from_neo4j(limit=limit)
        print(f"Neo4j 拉取到 {len(neo4j_idioms)} 个候选成语")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"Neo4j 获取成语失败: {exc}")
        neo4j_idioms = []

    for idiom in neo4j_idioms:
        if idiom and idiom not in seen:
            candidates.append(idiom)
            seen.add(idiom)

    return candidates


def crawl_all(candidates: list[str], inter_delay: float = 2.0) -> None:
    """对候选成语列表逐个爬取，使用显式传参 + inter_delay。"""
    import time
    
    for idx, ch in enumerate(candidates, start=1):
        print("=" * 60)
        print(f"[{idx}/{len(candidates)}] 爬取: {ch}")
        print("=" * 60)

        url = get_chengyu_url(ch, delay=0.5)
        if not url:
            print(f"无法获取 {ch} 的详情页 URL")
            # 即使获取失败也要保持延时节奏
            if idx < len(candidates):
                print(f"等待 {inter_delay} 秒后继续下一个...")
                time.sleep(inter_delay)
            continue

        details = extract_chengyu_details_from_url(url, delay=1)
        print_chengyu_data(details)
        print("\n完整 JSON 数据:")
        print(json.dumps(details, ensure_ascii=False, indent=2))
        
        # 显式控制项间延时
        if idx < len(candidates):  # 最后一项不需要延时
            print(f"等待 {inter_delay} 秒后继续下一个...")
            time.sleep(inter_delay)


def main() -> None:
    candidates = collect_candidates(limit=NEO4J_LIMIT)
    print(f"候选数: {len(candidates)}（5个硬编码 + {len(candidates)-5}个Neo4j），开始批量爬取...")
    crawl_all(candidates, inter_delay=1.0)


if __name__ == "__main__":
    main()