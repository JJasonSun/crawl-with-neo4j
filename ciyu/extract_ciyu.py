# -*- coding: utf-8 -*-
"""爬取汉语国学网站的词语（词典）信息。"""

import os
import time
import urllib.parse
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag
from common.crawl_runner import CrawlerConfig, run_crawl_main
from ciyu_DB import save_ciyu_to_db, get_word_list

# 默认批处理大小：每次处理的词语数量
DEFAULT_BATCH_SIZE = 1000
# 默认请求延迟：每个详情页请求之间的延迟（秒）
DEFAULT_REQUEST_DELAY = 0.0
# 默认搜索延迟：每个搜索请求之间的延迟（秒）
DEFAULT_SEARCH_DELAY = 0.0
# 最大随机抖动：为避免请求模式被识别，添加的随机延迟上限（秒）
DEFAULT_JITTER_MAX = 0.8
# 优雅关闭等待时间：收到中断信号后等待正在进行的请求完成的时间（秒）
DEFAULT_GRACEFUL_SHUTDOWN_WAIT = 3.0
# 数据库批处理大小：批量写入数据库的记录数
DB_BATCH_SIZE = 50
# 数据库刷新间隔：批量写入数据库的时间间隔（秒）
DB_FLUSH_INTERVAL = 3.0
# 重试退避基数：失败重试的基础延迟时间（秒）
RETRY_BACKOFF_BASE = 300
# 重试退避上限：失败重试的最大延迟时间（秒）
RETRY_BACKOFF_MAX = 15


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
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"获取词语 '{word}' 的 URL 时发生未知错误: {exc}")
        return None


# ========================
# HTML 解析
# ========================
def _extract_list_from_label(ci_attrs: Optional[Tag], label_text: str) -> List[str]:
    if not ci_attrs:
        return []
    label = ci_attrs.find("label", string=label_text)  # type: ignore
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
            pinyin_label = ci_attrs.find("label", string="拼音")  # type: ignore
            if pinyin_label:
                pinyin_span = pinyin_label.find_next_sibling("span")
                if pinyin_span:
                    data["pinyin"] = pinyin_span.get_text(strip=True)

            zhuyin_label = ci_attrs.find("label", string="注音")  # type: ignore
            if zhuyin_label:
                zhuyin_span = zhuyin_label.find_next_sibling("span")
                if zhuyin_span:
                    data["zhuyin"] = zhuyin_span.get_text(strip=True)

            pos_label = ci_attrs.find("label", string="词性")  # type: ignore
            if pos_label:
                pos_span = pos_label.find_next_sibling("span")
                if pos_span:
                    data["part_of_speech"] = pos_span.get_text(strip=True)

            data["synonyms"] = _extract_list_from_label(ci_attrs, "近义词")
            data["antonyms"] = _extract_list_from_label(ci_attrs, "反义词")

        # 网络解释作为主释义
        network_heading = soup.find("h3", string="网络解释")  # type: ignore
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
        raise
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": f"处理失败: {exc}"}


# ========================
# 通用爬取配置入口
# ========================
def build_crawler_config() -> CrawlerConfig:
    base_dir = os.path.dirname(__file__)

    return CrawlerConfig(
        name="词语",
        base_dir=base_dir,
        get_items=get_word_list,
        search_func=lambda wd, delay, session=None: get_ciyu_url(wd, delay=delay),
        detail_func=lambda url, delay, session=None: extract_ciyu_details_from_url(url, delay=delay),
        save_func=save_ciyu_to_db,
        label_key="word",
        db_batch_size=DB_BATCH_SIZE,
        db_flush_interval=DB_FLUSH_INTERVAL,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_request_delay=DEFAULT_REQUEST_DELAY,
        default_search_delay=DEFAULT_SEARCH_DELAY,
        default_jitter_max=DEFAULT_JITTER_MAX,
        default_graceful_wait=DEFAULT_GRACEFUL_SHUTDOWN_WAIT,
        retry_backoff_base=RETRY_BACKOFF_BASE,
        retry_backoff_max=RETRY_BACKOFF_MAX,
    )


if __name__ == "__main__":
    cfg = build_crawler_config()
    exit(run_crawl_main(cfg))
