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
NEO4J_LIMIT = 5


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
    try:
        neo4j_words = get_words_from_neo4j(limit=limit)
        if neo4j_words:
            print(f"🧠 Neo4j 拉取到 {len(neo4j_words)} 个备选词语")
        else:
            print("⚠️ Neo4j 未返回词语，只有硬编码词汇可用")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"⚠️ Neo4j 获取词语失败: {exc}")
        neo4j_words = []

    seen = set()
    combined = []
    for source in (COMMON_WORDS, neo4j_words):
        for word in source:
            if word and word not in seen:
                seen.add(word)
                combined.append(word)

    return combined or COMMON_WORDS[:]


def run_test(word: str) -> None:
    print("=" * 60)
    print(f"测试词语: {word}")
    print("=" * 60)

    url = get_ciyu_url(word)
    if not url:
        print(f"无法获取 {word} 的详情页 URL")
        return

    print(f"详情页 URL: {url}")
    details = extract_ciyu_details_from_url(url)
    print_ciyu_data(details)
    print("\nJSON 数据:")
    print(json.dumps(details, ensure_ascii=False, indent=2))


def main() -> None:
    candidates = collect_candidates(limit=NEO4J_LIMIT)
    choice = random.choice(candidates)
    run_test(choice)


if __name__ == "__main__":
    main()