# -*- coding: utf-8 -*-
"""
简单的错误词语重试脚本
读取所有 batch_*_errors.csv 文件中的错误词语，重新尝试爬取并保存到数据库。

使用示例：
    python retry_errors.py
"""
import os
import csv
import glob
import time

from extract_ciyu import get_ciyu_url, extract_ciyu_details_from_url
from ciyu_mysql import save_ciyu_to_db


def read_error_ciyus():
    """读取所有错误CSV文件中的词语"""
    error_ciyus = []
    error_files = glob.glob(os.path.join(os.path.dirname(__file__), 'batch_*_errors.csv'))
    
    for error_file in error_files:
        try:
            with open(error_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ciyu = row.get('ciyu', '').strip()
                    error = row.get('error', '').strip()
                    if ciyu:
                        error_ciyus.append((ciyu, error, os.path.basename(error_file)))
        except Exception as e:
            print(f"读取错误文件 {error_file} 失败: {e}")
    
    return error_ciyus


def retry_ciyu(ciyu, delay=1.0):
    """重试单个词语的爬取"""
    try:
        # 添加延迟避免请求过快
        time.sleep(delay)
        
        # 获取词语URL
        url_result = get_ciyu_url(ciyu)
        if isinstance(url_result, dict) and url_result.get('error'):
            return False, f"获取URL失败: {url_result.get('error')}"
        
        url = url_result
        if url is None:
            return False, "无法获取词语详情页URL"
        
        # 再次延迟
        time.sleep(delay)
        
        # 提取词语详情
        data = extract_ciyu_details_from_url(url)
        if isinstance(data, dict) and 'error' in data:
            return False, f"提取详情失败: {data.get('error')}"
        
        # 确保数据格式正确
        if 'data' not in data or not data.get('data'):
            data = {'url': url, 'data': {'ciyu': ciyu}}
        else:
            if not data['data'].get('ciyu'):
                data['data']['ciyu'] = ciyu
        
        # 保存到数据库
        success = save_ciyu_to_db(data)
        if success:
            return True, "成功保存到数据库"
        else:
            return False, "保存到数据库失败"
            
    except Exception as e:
        return False, f"处理异常: {str(e)}"


def main():
    print("开始处理错误词语...")
    
    # 读取所有错误词语
    error_ciyus = read_error_ciyus()
    
    if not error_ciyus:
        print("没有找到错误词语文件或文件为空")
        return 0
    
    print(f"找到 {len(error_ciyus)} 个错误词语")
    
    # 统计结果
    success_count = 0
    fail_count = 0
    results = []
    
    # 处理每个错误词语
    for i, (ciyu, original_error, file_name) in enumerate(error_ciyus, 1):
        print(f"\n[{i}/{len(error_ciyus)}] 处理词语: {ciyu} (来自 {file_name})")
        print(f"原错误: {original_error[:100]}{'...' if len(original_error) > 100 else ''}")
        
        success, message = retry_ciyu(ciyu, delay=1.5)
        
        if success:
            print(f"✓ 成功: {message}")
            success_count += 1
        else:
            print(f"✗ 失败: {message}")
            fail_count += 1
        
        results.append((ciyu, original_error, file_name, success, message))
    
    # 输出统计结果
    print(f"\n处理完成!")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"总计: {len(error_ciyus)}")
    
    # 保存重试结果
    if results:
        retry_result_file = os.path.join(os.path.dirname(__file__), 'retry_results.csv')
        with open(retry_result_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ciyu', 'original_error', 'source_file', 'retry_success', 'retry_message'])
            for result in results:
                writer.writerow(result)
        print(f"重试结果已保存到: {retry_result_file}")
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    exit(main())