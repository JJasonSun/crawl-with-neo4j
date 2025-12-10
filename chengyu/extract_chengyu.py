# -*- coding: utf-8 -*-
import requests
import urllib.parse
import time
import re
from bs4 import BeautifulSoup



def get_chengyu_url(chengyu, delay=0.5, session=None):
    """获取成语详情页面的最终URL，并做详情页有效性校验

    Args:
        chengyu: 成语字符串
        delay: 请求延时时间（秒），默认0.5秒

    Returns:
        str | None: 成语详情页面URL，若未能定位到详情页则返回 None
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    }

    search_url = f"https://www.hanyuguoxue.com/chengyu/search?words={urllib.parse.quote(chengyu)}"

    try:
        # 防止被封IP，添加延时（可由调用方控制抖动）
        if delay > 0:
            time.sleep(delay)

        sess = session or requests
        response = sess.get(search_url, headers=headers, allow_redirects=True, timeout=10)
        # if blocked/limited by server (status codes commonly used for rate limiting/WAF)
        if response.status_code in (429, 403, 503):
            return {'blocked': response.status_code, 'body': response.text[:500]}
        response.raise_for_status()

        # 校验是否为成语详情页：
        # 1. 页面包含成语标题 <h1>
        # 2. 标题文本与待查询成语基本一致（去掉空白后相等）
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        title_element = soup.find('h1')
        if title_element:
            page_title = title_element.get_text(strip=True)
            if page_title and page_title.replace(" ", "") == chengyu.replace(" ", ""):
                return response.url

        # 如果走到这里，说明当前 URL 不是明确的详情页，返回 None 交由上层记录为失败
        print(f"未能在搜索结果中识别到成语 '{chengyu}' 的详情页，返回 None")
        return None
    except requests.exceptions.RequestException as e:
        print(f"获取成语'{chengyu}'的URL失败: {str(e)}")
        return {'error': str(e)}
    except Exception as e:
        print(f"获取成语'{chengyu}'的URL时发生未知错误: {str(e)}")
        return {'error': str(e)}


def extract_chengyu_details_from_html(html_content, url=None):
    """
    从HTML内容中提取成语详细信息（不访问URL）
    Args:
        html_content: HTML内容字符串
        url: 页面URL（可选，用于返回结果中）
    Returns:
        dict: 包含成语信息的字典
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            "url": url,
            "data": {}
        }
        
        # 提取成语名称
        title_element = soup.find('h1')
        if title_element:
            result["data"]["chengyu"] = title_element.get_text().strip()
        
        # 提取拼音信息 - 从 ci-title div 中的 pinyin div
        pinyin_element = soup.find('div', class_='ci-title')
        if pinyin_element:
            pinyin_div = pinyin_element.find('div', class_='pinyin')
            if pinyin_div:
                pinyin_spans = pinyin_div.find_all('span')
                pinyin_text = ' '.join([span.get_text().strip() for span in pinyin_spans])
                result["data"]["pinyin"] = pinyin_text
        
        # 提取基本信息 - 从 ci-attrs div
        ci_attrs = soup.find('div', class_='ci-attrs')
        if ci_attrs:
            # 提取注音
            p_tags = ci_attrs.find_all('p')
            for p in p_tags:
                p_text = p.get_text().strip()
                if '注音' in p_text:
                    # 提取注音部分
                    zhuyin_match = re.search(r'注音[：:]\s*([^\n]+)', p_text)
                    if zhuyin_match:
                        result["data"]["zhuyin"] = zhuyin_match.group(1).strip()
                
                # 提取感情色彩
                if '感情' in p_text:
                    emotion_link = p.find('a')
                    if emotion_link:
                        emotion_text = emotion_link.get_text().strip()
                        result["data"]["emotion"] = emotion_text
                
                # 提取近义词
                if '近义词' in p_text:
                    synonyms_links = p.find_all('a')
                    synonyms = [link.get_text().strip() for link in synonyms_links]
                    result["data"]["synonyms"] = synonyms
                
                # 提取反义词
                if '反义词' in p_text:
                    antonyms_links = p.find_all('a')
                    antonyms = [link.get_text().strip() for link in antonyms_links]
                    result["data"]["antonyms"] = antonyms
        
        # 提取释义 - 从 ci-content div
        ci_content = soup.find('div', class_='ci-content')
        if ci_content:
            # 主要释义
            primary_explain = ci_content.find('p', class_='explain primary')
            if primary_explain:
                # 移除复制按钮
                copy_button = primary_explain.find('button', class_='btn-copy')
                if copy_button:
                    copy_button.decompose()
                explanation_text = primary_explain.get_text().strip()
                result["data"]["explanation"] = explanation_text
            
            # 出处、用法、例子
            ext_ps = ci_content.find_all('p', class_='ext')
            for p in ext_ps:
                p_text = p.get_text().strip()
                if '出处' in p_text:
                    source_match = re.search(r'出处[：:]\s*(.+)', p_text)
                    if source_match:
                        result["data"]["source"] = source_match.group(1).strip()
                elif '用法' in p_text:
                    usage_match = re.search(r'用法[：:]\s*(.+)', p_text)
                    if usage_match:
                        result["data"]["usage"] = usage_match.group(1).strip()
                elif '例子' in p_text:
                    example_match = re.search(r'例子[：:]\s*(.+)', p_text)
                    if example_match:
                        result["data"]["example"] = example_match.group(1).strip()
        
        # 提取英文翻译 - 从 ci-fanyi ol
        ci_fanyi = soup.find('ol', class_='ci-fanyi')
        if ci_fanyi:
            translation_items = []
            li_elements = ci_fanyi.find_all('li')
            for li in li_elements:
                label = li.find('label')
                if label:
                    language = label.get_text().strip()
                    # 移除label元素，获取纯翻译文本
                    label.decompose()
                    translation_text = li.get_text().strip()
                    translation_items.append(f"{language}: {translation_text}")
            result["data"]["translation"] = '; '.join(translation_items)
        
        return result
        
    except Exception as e:
        return {
            "url": url,
            "error": f"HTML解析失败: {str(e)}"
        }


def extract_chengyu_details_from_url(url, delay=1.0, session=None):
    """
    从成语详情页面URL提取完整信息
    Args:
        url: 成语详情页面URL
        delay: 请求延时时间（秒），默认1秒
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    }

    try:
        sess = session or requests
        response = sess.get(url, headers=headers, timeout=10)
        # detect blocked status
        if response.status_code in (429, 403, 503):
            return {
                'url': url,
                'error': 'blocked',
                'status': response.status_code,
                'body': response.text[:500]
            }
        response.raise_for_status()
        html_content = response.text

        # 防止被封IP，添加延时（可由调用方控制抖动）
        if delay > 0:
            time.sleep(delay)

        # 使用HTML解析函数
        return extract_chengyu_details_from_html(html_content, url)
        
    except requests.exceptions.RequestException as e:
        return {
            "url": url,
            "error": f"网络请求失败: {str(e)}"
        }
    except Exception as e:
        return {
            "url": url,
            "error": f"处理失败: {str(e)}"
        }