# -*- coding: utf-8 -*-
"""
成语爬虫测试程序（直接调用hanyuguoxue.py中的函数）
"""
import sys
import os
import json
import random

# 添加父目录到路径，以便导入hanyuguoxue模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hanyuguoxue import get_chengyu_url, extract_chengyu_details_from_url, get_idioms_from_neo4j

def test_single_chengyu(chengyu):
    """
    测试单个成语的爬取
    """
    print(f"测试成语: {chengyu}")
    print("-" * 60)
    
    # 获取URL
    print(f"正在获取 {chengyu} 的详情页面URL...")
    url = get_chengyu_url(chengyu, delay=0.5)
    
    if url:
        print(f"成功获取URL: {url}")
        
        # 提取详情
        print(f"正在爬取 {chengyu} 的详细信息...")
        chengyu_data = extract_chengyu_details_from_url(url, delay=1)
        
        print("\n" + "="*60)
        print("爬取结果详情")
        print("="*60)
        
        if 'error' in chengyu_data:
            print(f"爬取失败: {chengyu_data['error']}")
        else:
            data = chengyu_data.get('data', {})
            
            # 基本信息
            print(f"成语: {data.get('chengyu', 'N/A')}")
            print(f"拼音: {data.get('pinyin', 'N/A')}")
            print(f"注音: {data.get('zhuyin', 'N/A')}")
            print(f"感情色彩: {data.get('emotion', 'N/A')}")
            
            # 详细信息
            explanation = data.get('explanation', 'N/A')
            if explanation != 'N/A':
                print(f"释义: {explanation}")
            
            print(f"\n出处:")
            source = data.get('source', 'N/A')
            if source != 'N/A':
                print(f"   {source}")
            else:
                print("   无")
            
            print(f"\n用法:")
            usage = data.get('usage', 'N/A')
            if usage != 'N/A':
                print(f"   {usage}")
            else:
                print("   无")
            
            print(f"\n例句:")
            example = data.get('example', 'N/A')
            if example != 'N/A':
                print(f"   {example}")
            else:
                print("   无")
            
            # 近义词
            print(f"\n近义词:")
            synonyms = data.get('synonyms', [])
            if synonyms:
                for i, synonym in enumerate(synonyms, 1):
                    print(f"   {i}. {synonym}")
            else:
                print("   无")
            
            # 反义词
            print(f"\n反义词:")
            antonyms = data.get('antonyms', [])
            if antonyms:
                for i, antonym in enumerate(antonyms, 1):
                    print(f"   {i}. {antonym}")
            else:
                print("   无")
            
            # 英文翻译
            print(f"\n英文翻译:")
            translation = data.get('translation', 'N/A')
            if translation != 'N/A':
                print(f"   {translation}")
            else:
                print("   无")
        
        print("\n" + "="*60)
        print("完整JSON数据（用于调试）")
        print("="*60)
        print(json.dumps(chengyu_data, ensure_ascii=False, indent=2))
        
    else:
        print(f"无法获取 {chengyu} 的详情页面URL")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)

def test_random_chengyu_from_neo4j():
    """
    从Neo4j随机获取一个成语并完整爬取显示
    """
    print("=" * 80)
    print("从Neo4j随机获取一个成语并完整爬取")
    print("=" * 80)
    
    # 从Neo4j获取成语列表
    print("正在从Neo4j获取成语列表...")
    try:
        chengyu_list = get_idioms_from_neo4j(limit=100)  # 获取100个成语供随机选择
        if not chengyu_list:
            print("无法从Neo4j获取成语列表，使用预设成语")
            chengyu_list = ["一心一意", "三心二意", "画蛇添足", "守株待兔", "亡羊补牢"]
    except Exception as e:
        print(f"从Neo4j获取成语时出错: {e}")
        print("使用预设成语")
        chengyu_list = ["一心一意", "三心二意", "画蛇添足", "守株待兔", "亡羊补牢"]
    
    # 随机选择一个成语
    random_chengyu = random.choice(chengyu_list)
    print(f"随机选择成语: {random_chengyu}")
    
    # 调用单个成语测试函数，显示完整内容
    test_single_chengyu(random_chengyu)

if __name__ == "__main__":
    print("成语爬虫测试程序")
    print("正在从Neo4j随机获取成语进行测试...")
    test_random_chengyu_from_neo4j()