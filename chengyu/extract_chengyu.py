# -*- coding: utf-8 -*-
import requests
import urllib.parse
import time
import json
import re
from bs4 import BeautifulSoup

from chengyu_mysql import get_database_connection



def get_chengyu_url(chengyu, delay=0.5):
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
        # 防止被封IP，添加延时
        if delay > 0:
            time.sleep(delay)
            
        response = requests.get(search_url, headers=headers, allow_redirects=True, timeout=10)
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
        return None
    except Exception as e:
        print(f"获取成语'{chengyu}'的URL时发生未知错误: {str(e)}")
        return None


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


def extract_chengyu_details_from_url(url, delay=1):
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
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        
        # 防止被封IP，添加延时
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


def save_chengyu_to_db(chengyu_data):
    """
    将成语数据保存到数据库
    """
    connection = get_database_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()

        # 开始事务
        connection.begin()

        # 提取成语名称
        chengyu = ""
        if 'data' in chengyu_data and 'chengyu' in chengyu_data['data']:
            chengyu = chengyu_data['data']['chengyu']

        # 如果有错误信息，跳过保存（不写入 error 行）
        if 'error' in chengyu_data:
            # 上层会把无法获取 URL 等情况记为失败，这里不再创建错误记录
            connection.rollback()
            return False

        # 保存完整数据（基础信息）——仅当存在近义词或反义词时才写入
        data = chengyu_data.get('data', {})
        synonyms = data.get('synonyms', []) or []
        antonyms = data.get('antonyms', []) or []

        # 无论是否存在近/反义词，解析成功的基础信息都应写入基础表（只在有近/反义词时写入关系表）

        sql = """
        INSERT INTO hanyuguoxue_chengyu
        (`chengyu`, `url`, `pinyin`, `zhuyin`, `emotion`, `explanation`, 
         `source`, `usage`, `example`, `synonyms`, `antonyms`, `translation`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        `url` = VALUES(`url`),
        `pinyin` = VALUES(`pinyin`),
        `zhuyin` = VALUES(`zhuyin`),
        `emotion` = VALUES(`emotion`),
        `explanation` = VALUES(`explanation`),
        `source` = VALUES(`source`),
        `usage` = VALUES(`usage`),
        `example` = VALUES(`example`),
        `synonyms` = VALUES(`synonyms`),
        `antonyms` = VALUES(`antonyms`),
        `translation` = VALUES(`translation`),
        updated_at = CURRENT_TIMESTAMP
        """
        cursor.execute(sql, (
            chengyu,
            chengyu_data.get('url', ''),
            data.get('pinyin', ''),
            data.get('zhuyin', ''),
            data.get('emotion', ''),
            data.get('explanation', ''),
            data.get('source', ''),
            data.get('usage', ''),
            data.get('example', ''),
            json.dumps(synonyms, ensure_ascii=False),
            json.dumps(antonyms, ensure_ascii=False),
            data.get('translation', '')
        ))

        # 确保主成语有 id
        cursor.execute("SELECT id FROM hanyuguoxue_chengyu WHERE chengyu=%s", (chengyu,))
        row = cursor.fetchone()
        if not row:
            # 应该不发生，但作为防御再尝试一次插入最小记录
            cursor.execute("INSERT IGNORE INTO hanyuguoxue_chengyu (chengyu) VALUES (%s)", (chengyu,))
            cursor.execute("SELECT id FROM hanyuguoxue_chengyu WHERE chengyu=%s", (chengyu,))
            row = cursor.fetchone()
        if not row:
            raise RuntimeError('无法获取主成语 id')
        main_id = row['id']

        # 辅助函数：规范化词
        def normalize_term(t):
            if not t:
                return None
            return t.strip()

        # 批量确保词存在并返回 name->id 映射
        def ensure_terms_have_ids(term_list):
            terms = [normalize_term(t) for t in set(term_list) if t and normalize_term(t)]
            if not terms:
                return {}
            # 批量 INSERT IGNORE 最小记录
            insert_vals = [(t,) for t in terms]
            cursor.executemany("INSERT IGNORE INTO hanyuguoxue_chengyu (chengyu) VALUES (%s)", insert_vals)
            # 批量查询 id
            placeholders = ','.join(['%s'] * len(terms))
            cursor.execute(f"SELECT id, chengyu FROM hanyuguoxue_chengyu WHERE chengyu IN ({placeholders})", terms)
            rows = cursor.fetchall()
            return {r['chengyu']: r['id'] for r in rows}

        # 插入关系（min_id,max_id）
        def insert_relations_for(main_id, related_terms, relation_type):
            if not related_terms:
                return
            # 获取或创建 related ids
            term_map = ensure_terms_have_ids(related_terms + [chengyu])
            values = []
            for t in related_terms:
                tn = normalize_term(t)
                if not tn:
                    continue
                rid = term_map.get(tn)
                if not rid or rid == main_id:
                    continue
                a = min(main_id, rid)
                b = max(main_id, rid)
                values.append((a, b, relation_type))
            if values:
                cursor.executemany(
                    "INSERT IGNORE INTO chengyu_relation (min_id, max_id, relation_type) VALUES (%s, %s, %s)",
                    values
                )

        # 处理近义词与反义词
        synonyms = data.get('synonyms', []) or []
        antonyms = data.get('antonyms', []) or []
        insert_relations_for(main_id, synonyms, 'synonym')
        insert_relations_for(main_id, antonyms, 'antonym')

        # 一切正常，提交事务
        connection.commit()
        return True

    except Exception as e:
        print(f"保存成语数据到数据库失败: {e}")
        try:
            connection.rollback()
        except Exception:
            pass
        return False
    finally:
        connection.close()