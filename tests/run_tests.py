# -*- coding: utf-8 -*-
"""
测试运行器
运行所有测试并生成报告。
"""
import unittest
import sys
import os
from io import StringIO

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """运行所有测试"""
    # 发现并加载所有测试
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # 创建测试运行器
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        descriptions=True,
        failfast=False
    )
    
    # 运行测试
    result = runner.run(suite)
    
    # 输出结果
    output = stream.getvalue()
    print(output)
    
    # 生成摘要
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
    success = total_tests - failures - errors - skipped
    
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print(f"总测试数: {total_tests}")
    print(f"成功: {success}")
    print(f"失败: {failures}")
    print(f"错误: {errors}")
    print(f"跳过: {skipped}")
    print(f"成功率: {(success/total_tests*100):.1f}%" if total_tests > 0 else "成功率: 0%")
    
    if failures > 0:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if errors > 0:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    return result.wasSuccessful()


def run_specific_test(test_module):
    """运行特定测试模块"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_module)
    
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        descriptions=True,
        failfast=False
    )
    
    result = runner.run(suite)
    output = stream.getvalue()
    print(output)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 运行特定测试
        test_module = sys.argv[1]
        print(f"运行测试模块: {test_module}")
        success = run_specific_test(test_module)
    else:
        # 运行所有测试
        print("运行所有测试...")
        success = run_all_tests()
    
    sys.exit(0 if success else 1)