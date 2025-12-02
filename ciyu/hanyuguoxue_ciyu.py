# -*- coding: utf-8 -*-
"""爬取汉语国学网站的词语（词典）信息。"""

import json
import time
import urllib.parse
from typing import Dict, List, Optional

import pymysql
import requests
from bs4 import BeautifulSoup
from neo4j import GraphDatabase

# ========================
# 数据库配置
# ========================
neo4j_config = {
    "uri": "bolt://8.153.207.172:7687",
    "user": "neo4j",
    "password": "xtxzhu2u",
}

mysql_config = {
    "host": "8.153.207.172",
    "user": "root",
    "password": "Restart1128",
    "database": "lab_education",
    "port": 3307,
}


# ========================
# Neo4j 读取词语列表
# ========================
def get_words_from_neo4j(limit: Optional[int] = None) -> List[str]:
    """从 Neo4j 获取词语（Word 节点）。"""
    driver = GraphDatabase.driver(
        neo4j_config["uri"],
        auth=(neo4j_config["user"], neo4j_config["password"]),
    )
    words: List[str] = []
    try:
        with driver.session() as session:
            if limit:
                query = "MATCH (n:Word) RETURN n.name AS name LIMIT $limit"
                result = session.run(query, limit=limit)
            else:
                query = "MATCH (n:Word) RETURN n.name AS name"
                result = session.run(query)
            for record in result:
                if record["name"]:
                    words.append(record["name"])
    finally:
        driver.close()
    return words


# ========================
# URL 获取与验证
# ========================
def get_ciyu_url(word: str, delay: float = 0.5) -> Optional[str]:
    """通过搜索接口获取词语详情页 URL，并校验是否为正确详情页。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    }

    search_url = (
        f"https://www.hanyuguoxue.com/cidian/search?words={urllib.parse.quote(word)}"
    )

    try:
        if delay > 0:
            time.sleep(delay)

        response = requests.get(search_url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title_element = soup.find("h1")
        if title_element:
            page_word = title_element.get_text(strip=True)
            if page_word and page_word.replace(" ", "") == word.replace(" ", ""):
                return response.url

        print(f"未能在搜索结果中确认词语 '{word}' 的详情页，返回 None")
        return None
    except requests.RequestException as exc:
        print(f"获取词语 '{word}' 的 URL 失败: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"获取词语 '{word}' 的 URL 时发生未知错误: {exc}")
        return None


# ========================
# HTML 解析
# ========================
def _extract_list_from_label(ci_attrs: Optional[BeautifulSoup], label_text: str) -> List[str]:
    if not ci_attrs:
        return []
    label = ci_attrs.find("label", string=label_text)
    if not label:
        return []
    container = label.parent
    if not container:
        return []
    links = container.select("span.ci-list a")
    return [link.get_text(strip=True) for link in links if link.get_text(strip=True)]


def extract_ciyu_details_from_html(html_content: str, url: Optional[str] = None) -> Dict:
    """从 HTML 内容中解析词语的结构化信息。"""
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        result: Dict = {"url": url, "data": {}}
        data = result["data"]

        # 词语、拼音与常用词标记
        title_wrap = soup.find("div", class_="ci-title-wrap")
        if title_wrap:
            title_element = title_wrap.find("h1")
            if title_element:
                data["word"] = title_element.get_text(strip=True)

            pinyin_div = title_wrap.find("div", class_="pinyin")
            if pinyin_div:
                spans = [span.get_text(strip=True) for span in pinyin_div.find_all("span")]
                data["pinyin"] = " ".join([s for s in spans if s])

            common_tag = title_wrap.find("div", class_="ci-tag")
            data["is_common"] = (
                common_tag is not None and "常用词" in common_tag.get_text(strip=True)
            )

        # 基础属性：拼音、注音、词性、近反义词等
        ci_attrs = soup.find("div", class_="ci-attrs")
        if ci_attrs:
            # 拼音 (更稳定)
            pinyin_label = ci_attrs.find("label", string="拼音")
            if pinyin_label:
                pinyin_span = pinyin_label.find_next_sibling("span")
                if pinyin_span:
                    data["pinyin"] = pinyin_span.get_text(strip=True)

            zhuyin_label = ci_attrs.find("label", string="注音")
            if zhuyin_label:
                zhuyin_span = zhuyin_label.find_next_sibling("span")
                if zhuyin_span:
                    data["zhuyin"] = zhuyin_span.get_text(strip=True)

            pos_label = ci_attrs.find("label", string="词性")
            if pos_label:
                pos_span = pos_label.find_next_sibling("span")
                if pos_span:
                    data["part_of_speech"] = pos_span.get_text(strip=True)

            data["synonyms"] = _extract_list_from_label(ci_attrs, "近义词")
            data["antonyms"] = _extract_list_from_label(ci_attrs, "反义词")

        # 网络解释作为主释义
        network_heading = soup.find("h3", string="网络解释")
        if network_heading:
            content_block = network_heading.parent.find_next_sibling("div")
            if content_block:
                data["definition"] = content_block.get_text(" ", strip=True)

        return result
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": f"HTML 解析失败: {exc}"}


# ========================
# URL 解析入口
# ========================
def extract_ciyu_details_from_url(url: str, delay: float = 1.0) -> Dict:
    """请求词语详情页并解析数据。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text

        if delay > 0:
            time.sleep(delay)

        return extract_ciyu_details_from_html(html, url=url)
    except requests.RequestException as exc:
        return {"url": url, "error": f"网络请求失败: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": f"处理失败: {exc}"}


# ========================
# MySQL 读写
# ========================
def get_database_connection():
    try:
        return pymysql.connect(
            host=mysql_config["host"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
            port=mysql_config["port"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"数据库连接失败: {exc}")
        return None


def save_ciyu_to_db(ciyu_data: Dict) -> bool:
    """将解析结果写入 MySQL。"""
    connection = get_database_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        data = ciyu_data.get("data", {})
        word = data.get("word", "")

        if "error" in ciyu_data:
            sql = (
                "INSERT INTO hanyuguoxue_ciyu (word, url, error) "
                "VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE url = VALUES(url), error = VALUES(error), "
                "updated_at = CURRENT_TIMESTAMP"
            )
            cursor.execute(sql, (word, ciyu_data.get("url", ""), ciyu_data["error"]))
        else:
            sql = (
                "INSERT INTO hanyuguoxue_ciyu "
                "(word, url, pinyin, zhuyin, part_of_speech, is_common, "
                "definition, synonyms, antonyms) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "url = VALUES(url), "
                "pinyin = VALUES(pinyin), "
                "zhuyin = VALUES(zhuyin), "
                "part_of_speech = VALUES(part_of_speech), "
                "is_common = VALUES(is_common), "
                "definition = VALUES(definition), "
                "synonyms = VALUES(synonyms), "
                "antonyms = VALUES(antonyms), "
                "updated_at = CURRENT_TIMESTAMP"
            )
            cursor.execute(
                sql,
                (
                    word,
                    ciyu_data.get("url", ""),
                    data.get("pinyin", ""),
                    data.get("zhuyin", ""),
                    data.get("part_of_speech", ""),
                    int(bool(data.get("is_common"))),
                    data.get("definition", ""),
                    json.dumps(data.get("synonyms", []), ensure_ascii=False),
                    json.dumps(data.get("antonyms", []), ensure_ascii=False),
                ),
            )

        connection.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"保存词语数据失败: {exc}")
        connection.rollback()
        return False
    finally:
        connection.close()


# ========================
# 主爬虫流程
# ========================
def crawl_all_ciyu(
    limit: Optional[int] = None,
    start_index: int = 0,
    request_delay: float = 1.0,
    search_delay: float = 0.5,
):
    """批量爬取词语详情。"""
    print("正在从 Neo4j 获取词语列表……")
    if start_index == 0 and limit:
        word_list = get_words_from_neo4j(limit=limit)
    else:
        word_list = get_words_from_neo4j(limit=None)

    if not word_list:
        print("未获取到词语列表")
        return

    total_words = len(word_list)
    if start_index >= total_words:
        print(f"起始索引 {start_index} 超出范围（总计 {total_words} 条）")
        return

    end_index = total_words
    if limit:
        end_index = min(start_index + limit, total_words)

    target_list = word_list[start_index:end_index]

    success = 0
    failed = 0

    print(f"开始爬取词语：范围 {start_index + 1}-{end_index}/{total_words}")
    print("=" * 60)

    for idx, word in enumerate(target_list, start=start_index + 1):
        try:
            print(f"【{idx:4d}/{end_index}】正在爬取：{word}")
            url = get_ciyu_url(word, delay=search_delay)
            if not url:
                failed += 1
                print(f"  ❌ 无法获取 {word} 的详情页面 URL")
                continue

            ciyu_data = extract_ciyu_details_from_url(url, delay=request_delay)
            if save_ciyu_to_db(ciyu_data):
                success += 1
                print(f"  ✅ 成功保存：{word}")
                if "data" in ciyu_data:
                    data = ciyu_data["data"]
                    snippet = [
                        f"拼音: {data.get('pinyin', '')}",
                        f"词性: {data.get('part_of_speech', '')}",
                    ]
                    print("    " + " | ".join(snippet))
            else:
                failed += 1
                print(f"  ❌ 保存失败：{word}")

            if idx % 10 == 0:
                progress = idx / end_index * 100
                print(
                    f"进度 {progress:.1f}% (成功: {success}, 失败: {failed})"
                )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ❌ 爬取 {word} 时发生错误: {exc}")
            continue

    print("=" * 60)
    print("爬取完成！")
    print(f"处理词语数: {end_index - start_index}")
    print(f"成功: {success}")
    print(f"失败: {failed}")
    total = success + failed
    if total > 0:
        print(f"成功率: {success / total * 100:.2f}%")


# ========================
# CLI 入口
# ========================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python hanyuguoxue.py [命令] [参数]")
        print("命令:")
        print("  crawl [limit] [start_index] [request_delay] [search_delay]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "crawl":
        limit_val: Optional[int] = None
        start_idx = 0
        request_delay = 1.0
        search_delay = 0.5

        if len(sys.argv) >= 3 and sys.argv[2] != "None":
            limit_val = int(sys.argv[2])
        if len(sys.argv) >= 4:
            start_idx = int(sys.argv[3])
        if len(sys.argv) >= 5:
            request_delay = float(sys.argv[4])
        if len(sys.argv) >= 6:
            search_delay = float(sys.argv[5])

        print("开始爬取词语数据……")
        print(f"限制数量: {limit_val if limit_val else '全部'}")
        print(f"起始索引: {start_idx}")
        print(f"请求延时: {request_delay}s")
        print(f"搜索延时: {search_delay}s")
        print("=" * 60)

        crawl_all_ciyu(
            limit=limit_val,
            start_index=start_idx,
            request_delay=request_delay,
            search_delay=search_delay,
        )
    else:
        print(f"未知命令: {command}")
        sys.exit(1)
