# -*- coding: utf-8 -*-
"""混合硬编码与 Neo4j 成语进行爬虫回归测试。"""

import json
import os
import random
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hanyuguoxue_chengyu import (
    extract_chengyu_details_from_url,
    get_chengyu_url,
    get_idioms_from_neo4j,
)

COMMON_CHENGYU = [
    "一心一意",
    "三心二意",
    "守株待兔",
    "画蛇添足",
    "亡羊补牢",
]
NEO4J_LIMIT = 5


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
    try:
        neo4j_idioms = get_idioms_from_neo4j(limit=limit)
        if neo4j_idioms:
            print(f"🧠 Neo4j 拉取到 {len(neo4j_idioms)} 个候选成语")
        else:
            print("⚠️ Neo4j 未返回成语，仅使用硬编码列表")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"⚠️ Neo4j 获取成语失败: {exc}")
        neo4j_idioms = []

    seen = set()
    combined = []
    for source in (COMMON_CHENGYU, neo4j_idioms):
        for item in source:
            if item and item not in seen:
                seen.add(item)
                combined.append(item)

    return combined or COMMON_CHENGYU[:]


def run_test(chengyu: str) -> None:
    print("=" * 60)
    print(f"测试成语: {chengyu}")
    print("=" * 60)

    url = get_chengyu_url(chengyu)
    if not url:
        print(f"无法获取 {chengyu} 的详情页 URL")
        return

    print(f"详情页 URL: {url}")
    details = extract_chengyu_details_from_url(url)
    print_chengyu_data(details)
    print("\n完整 JSON 数据:")
    print(json.dumps(details, ensure_ascii=False, indent=2))


def main() -> None:
    candidates = collect_candidates(limit=NEO4J_LIMIT)
    choice = random.choice(candidates)
    run_test(choice)


if __name__ == "__main__":
    main()