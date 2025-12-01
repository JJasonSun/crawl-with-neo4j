# -*- coding: utf-8 -*-
import requests
import urllib.parse
import time
import json
import re
import pymysql
from bs4 import BeautifulSoup
from neo4j import GraphDatabase

# Neo4j配置
neo4j_config = {
    "uri": "bolt://8.153.207.172:7687",
    "user": "neo4j",
    "password": "xtxzhu2u"
}

# MySQL数据库配置
mysql_config = {
    "host": "8.153.207.172",
    "user": "root",
    "password": "Restart1128",
    "database": "lab_education",
    "port": 3307
}

def get_idioms_from_neo4j(limit=None):
    """
    从Neo4j数据库获取成语列表
    """
    driver = GraphDatabase.driver(neo4j_config["uri"], auth=(neo4j_config["user"], neo4j_config["password"]))
    idiom_list = []
    with driver.session() as session:
        if limit:
            query = "MATCH (n:Idiom) RETURN n.name AS name LIMIT $limit"
            result = session.run(query, limit=limit)
        else:
            query = "MATCH (n:Idiom) RETURN n.name AS name"
            result = session.run(query)
        for record in result:
            idiom_list.append(record["name"])
    driver.close()
    return idiom_list


def get_chengyu_url(chengyu):
    """
    获取成语详情页面的最终URL
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    }

    search_url = f"https://www.hanyuguoxue.com/chengyu/search?words={urllib.parse.quote(chengyu)}"

    try:
        response = requests.get(search_url, headers=headers, allow_redirects=True, timeout=10)
        return response.url
    except:
        return None


def extract_chengyu_details_from_url(url):
    """
    从成语详情页面URL提取完整信息
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
        time.sleep(1)
        
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
        
        # 提取结构信息 - 从 ci-cards ul
        ci_cards = soup.find('div', class_='ci-cards')
        if ci_cards:
            structure_info = {}
            li_elements = ci_cards.find_all('li')
            for li in li_elements:
                span = li.find('span')
                if span:
                    key = span.get_text().strip()
                    link = li.find('a')
                    if link:
                        value = link.get_text().strip()
                        structure_info[key] = value
            result["data"]["structure"] = structure_info
        
        return result
        
    except Exception as e:
        return {
            "url": url,
            "error": str(e)
        }


def get_database_connection():
    """
    获取MySQL数据库连接
    """
    try:
        connection = pymysql.connect(
            host=mysql_config["host"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
            port=mysql_config["port"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None





def save_chengyu_to_db(chengyu_data):
    """
    将成语数据保存到数据库
    """
    connection = get_database_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        
        # 提取成语名称
        chengyu = ""
        if 'data' in chengyu_data and 'chengyu' in chengyu_data['data']:
            chengyu = chengyu_data['data']['chengyu']
        
        # 如果有错误信息，保存错误记录
        if 'error' in chengyu_data:
            sql = """
            INSERT INTO hanyuguoxue_chengyu
            (chengyu, url, error)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
            url = VALUES(url),
            error = VALUES(error),
            updated_at = CURRENT_TIMESTAMP
            """
            cursor.execute(sql, (
                chengyu,
                chengyu_data.get('url', ''),
                chengyu_data['error']
            ))
        else:
            # 保存完整数据
            data = chengyu_data.get('data', {})
            sql = """
            INSERT INTO hanyuguoxue_chengyu
            (chengyu, url, pinyin, zhuyin, fanti, emotion, explanation, 
             source, usage, example, synonyms, antonyms, translation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            url = VALUES(url),
            pinyin = VALUES(pinyin),
            zhuyin = VALUES(zhuyin),
            fanti = VALUES(fanti),
            emotion = VALUES(emotion),
            explanation = VALUES(explanation),
            source = VALUES(source),
            usage = VALUES(usage),
            example = VALUES(example),
            synonyms = VALUES(synonyms),
            antonyms = VALUES(antonyms),
            translation = VALUES(translation),
            updated_at = CURRENT_TIMESTAMP
            """
            cursor.execute(sql, (
                chengyu,
                chengyu_data.get('url', ''),
                data.get('pinyin', ''),
                data.get('zhuyin', ''),
                data.get('fanti', ''),
                data.get('emotion', ''),
                data.get('explanation', ''),
                data.get('source', ''),
                data.get('usage', ''),
                data.get('example', ''),
                json.dumps(data.get('synonyms', []), ensure_ascii=False),
                json.dumps(data.get('antonyms', []), ensure_ascii=False),
                data.get('translation', '')
            ))
        
        connection.commit()
        return True
        
    except Exception as e:
        print(f"保存成语数据到数据库失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def crawl_all_chengyu(limit=None, start_index=0):
    """
    批量爬取所有成语数据
    Args:
        limit: 限制爬取数量，None表示爬取全部
        start_index: 开始索引，用于断点续爬
    """
    # 注意：使用前请先运行 create_table.py 创建数据表
    
    # 获取成语列表
    print("正在从Neo4j获取成语列表...")
    chengyu_list = get_idioms_from_neo4j(limit=None)  # 获取所有成语
    
    if not chengyu_list:
        print("未获取到成语列表")
        return
    
    total_chengyu = len(chengyu_list)
    print(f"共获取到 {total_chengyu} 个成语")
    
    # 应用限制和起始索引
    if start_index >= total_chengyu:
        print(f"起始索引 {start_index} 超出范围，总成语数: {total_chengyu}")
        return
    
    end_index = total_chengyu
    if limit:
        end_index = min(start_index + limit, total_chengyu)
    
    chengyu_list = chengyu_list[start_index:end_index]
    
    successful_crawls = 0
    failed_crawls = 0
    
    print(f"开始爬取成语，范围: {start_index+1}-{end_index}/{total_chengyu}")
    print("=" * 60)
    
    for i, chengyu in enumerate(chengyu_list, start=start_index + 1):
        try:
            print(f"【{i:4d}/{end_index}】正在爬取: {chengyu}")
            
            # 获取成语详情页面URL
            url = get_chengyu_url(chengyu)
            if not url:
                print(f"  ❌ 无法获取 {chengyu} 的详情页面URL")
                failed_crawls += 1
                continue
            
            # 提取成语详情
            chengyu_data = extract_chengyu_details_from_url(url)
            
            # 保存到数据库
            if save_chengyu_to_db(chengyu_data):
                successful_crawls += 1
                print(f"  ✅ 成功保存: {chengyu}")
                
                # 显示部分信息
                if 'data' in chengyu_data:
                    data = chengyu_data['data']
                    if 'pinyin' in data:
                        print(f"    拼音: {data['pinyin']}")
                    if 'emotion' in data:
                        print(f"    感情: {data['emotion']}")
                    if 'synonyms' in data and data['synonyms']:
                        print(f"    近义词: {', '.join(data['synonyms'][:3])}{'...' if len(data['synonyms']) > 3 else ''}")
                    if 'antonyms' in data and data['antonyms']:
                        print(f"    反义词: {', '.join(data['antonyms'][:3])}{'...' if len(data['antonyms']) > 3 else ''}")
            else:
                failed_crawls += 1
                print(f"  ❌ 保存失败: {chengyu}")
            
            # 每处理10个成语显示一次进度
            if i % 10 == 0:
                progress = i / end_index * 100
                print(f"进度: {progress:.1f}% (成功: {successful_crawls}, 失败: {failed_crawls})")
            
        except Exception as e:
            failed_crawls += 1
            print(f"  ❌ 爬取 {chengyu} 时发生错误: {e}")
            continue
    
    print("=" * 60)
    print(f"爬取完成！")
    print(f"处理成语数: {end_index - start_index}")
    print(f"成功爬取: {successful_crawls}")
    print(f"失败爬取: {failed_crawls}")
    print(f"成功率: {successful_crawls/(successful_crawls+failed_crawls)*100:.2f}%" if (successful_crawls+failed_crawls) > 0 else "0%")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python hanyuguoxue.py [命令] [参数]")
        print("命令:")
        print("  crawl [limit] [start_index] - 爬取成语数据")
        print("示例:")
        print("  python hanyuguoxue.py crawl 10 0    # 爬取前10个成语")
        print("  python hanyyuoxue.py crawl 100 50   # 从第51个开始爬取100个成语")
        print("  python hanyuguoxue.py crawl          # 爬取所有成语")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "crawl":
        limit = None
        start_index = 0
        
        if len(sys.argv) >= 3:
            limit = int(sys.argv[2])
        
        if len(sys.argv) >= 4:
            start_index = int(sys.argv[3])
        
        print(f"🚀 开始爬取成语数据...")
        print(f"限制数量: {limit if limit else '全部'}")
        print(f"起始索引: {start_index}")
        print("="*60)
        
        crawl_all_chengyu(limit=limit, start_index=start_index)
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)