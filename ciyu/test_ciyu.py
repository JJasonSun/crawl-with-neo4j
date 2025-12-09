# -*- coding: utf-8 -*-
"""混合硬编码与 Neo4j 词汇的测试入口。"""

import json
import os
import random
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hanyuguoxue_ciyu import (
    extract_ciyu_details_from_url,
    get_ciyu_url,
    get_words_from_neo4j,
)

COMMON_WORDS = [
    "欣赏",
    "喜欢",
    "快乐",
    "学习",
    "努力",
]
NEO4J_LIMIT = 45


def print_ciyu_data(ciyu_data: dict) -> None:
    if "error" in ciyu_data:
        print(f"❌ 爬取失败: {ciyu_data['error']}")
        return

    data = ciyu_data.get("data", {})
    print(f"词语: {data.get('word', 'N/A')}")
    print(f"拼音: {data.get('pinyin', 'N/A')}")
    print(f"词性: {data.get('part_of_speech', 'N/A')}")
    print(f"常用词: {'是' if data.get('is_common') else '否'}")
    print(f"网络解释: {data.get('definition', 'N/A')}")

    synonyms = data.get("synonyms", [])
    print("\n近义词:")
    if synonyms:
        for idx, synonym in enumerate(synonyms, start=1):
            print(f"  {idx}. {synonym}")
    else:
        print("  无")

    antonyms = data.get("antonyms", [])
    print("\n反义词:")
    if antonyms:
        for idx, antonym in enumerate(antonyms, start=1):
            print(f"  {idx}. {antonym}")
    else:
        print("  无")


def collect_candidates(limit: int) -> list[str]:
    """返回 5 个硬编码词语加上从 Neo4j 拉取的候选，按实际数量拼接。"""
    candidates = COMMON_WORDS.copy()
    seen = set(candidates)

    try:
        neo4j_words = get_words_from_neo4j(limit=limit)
        print(f"Neo4j 拉取到 {len(neo4j_words)} 个候选词语")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"Neo4j 获取词语失败: {exc}")
        neo4j_words = []

    for word in neo4j_words:
        if word and word not in seen:
            candidates.append(word)
            seen.add(word)

    return candidates


def crawl_all(candidates: list[str], inter_delay: float = 1.0) -> None:
    """对候选词语列表逐个爬取，使用显式传参 + inter_delay。"""
    import time
    
    for idx, word in enumerate(candidates, start=1):
        print("=" * 60)
        print(f"[{idx}/{len(candidates)}] 爬取: {word}")
        print("=" * 60)

        url = get_ciyu_url(word, delay=0.5)
        if not url:
            print(f"无法获取 {word} 的详情页 URL")
            # 即使获取失败也要保持延时节奏
            if idx < len(candidates):
                print(f"等待 {inter_delay} 秒后继续下一个...")
                time.sleep(inter_delay)
            continue

        details = extract_ciyu_details_from_url(url, delay=1.0)
        print_ciyu_data(details)
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