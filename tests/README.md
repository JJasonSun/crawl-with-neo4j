# 测试文档

本目录包含项目的所有测试用例，用于验证代码质量和功能正确性。

## 测试结构

```
tests/
├── __init__.py          # 测试包初始化
├── test_database.py     # 数据库操作测试
├── test_logger.py       # 日志系统测试
├── test_exceptions.py   # 异常处理测试
├── test_connections.py  # 数据库连接测试
├── run_tests.py         # 测试运行器
└── README.md           # 本文档
```

## 测试覆盖范围

### 1. 数据库操作测试 (test_database.py)

测试成语和词语数据库操作的基本功能：

- **ChengyuDB测试**：
  - 测试模式下的保存功能
  - MySQL连接和保存操作
  - 表名和字段名获取
  - Neo4j标签获取

- **CiyuDB测试**：
  - 测试模式下的保存功能
  - MySQL连接和保存操作
  - 表名和字段名获取
  - Neo4j标签获取

### 2. 数据库连接测试 (test_connections.py)

测试真实的数据库连接功能：

- **MySQL连接测试**：
  - 真实MySQL数据库连接
  - 连接参数验证
  - 连接状态检查

- **Neo4j连接测试**：
  - 真实Neo4j数据库连接
  - 认证信息验证
  - 连接状态检查

- **批量测试**：
  - 同时测试所有数据库连接
  - 综合连接状态报告

### 3. 日志系统测试 (test_logger.py)

测试结构化日志记录功能：

- **日志级别测试**：
  - DEBUG、INFO、WARNING、ERROR、CRITICAL
  - JSON格式验证
  - 额外数据记录

- **专用日志方法**：
  - 爬取开始/成功/错误日志
  - 数据库操作日志
  - 日志器获取函数

### 4. 异常处理测试 (test_exceptions.py)

测试自定义异常类的功能：

- **异常类测试**：
  - 基础异常类功能
  - 各类特定异常属性
  - 错误码验证

- **继承关系测试**：
  - 异常类继承层次
  - 多参数异常构造



## 运行测试

### 运行所有测试

```bash
cd tests
python run_tests.py
```

### 运行特定测试模块

```bash
cd tests
python run_tests.py test_database
python run_tests.py test_logger
python run_tests.py test_exceptions
python run_tests.py test_connections
```

### 使用unittest直接运行

```bash
cd tests
python -m unittest test_database.py
python -m unittest test_logger.py
python -m unittest test_exceptions.py
python -m unittest test_connections.py
```

## 测试报告

测试运行后会生成详细的报告，包括：

- **测试摘要**：
  - 总测试数
  - 成功/失败/错误/跳过数量
  - 成功率

- **失败详情**：
  - 失败的测试用例
  - 错误信息和堆栈跟踪

- **错误详情**：
  - 出现异常的测试用例
  - 异常类型和消息

## 测试环境

测试使用Mock对象模拟外部依赖，确保：

1. **隔离性**：测试不依赖真实的数据库连接
2. **可重复性**：测试结果稳定一致
3. **快速性**：测试执行速度快

## 添加新测试

1. 创建新的测试文件，命名格式为 `test_*.py`
2. 继承 `unittest.TestCase` 类
3. 编写测试方法，方法名以 `test_` 开头
4. 使用 `self.assert*` 方法进行断言
5. 在 `run_tests.py` 中添加新测试（如果需要）

## 测试最佳实践

1. **命名规范**：测试文件和方法使用描述性名称
2. **独立性**：每个测试用例应该独立运行
3. **可读性**：测试代码应该清晰易懂
4. **覆盖率**：确保测试覆盖主要功能和边界情况
5. **Mock使用**：适当使用Mock对象隔离外部依赖

## 持续集成

这些测试可以集成到CI/CD流水线中，确保代码质量：

```yaml
# 示例GitHub Actions配置
- name: Run Tests
  run: |
    cd tests
    python run_tests.py
```

## 故障排除

### 常见问题

1. **导入错误**：确保项目根目录在Python路径中
2. **Mock失败**：检查Mock对象的配置和调用
3. **断言失败**：验证预期值和实际值的类型和内容

### 调试技巧

1. 使用 `-v` 参数获取详细输出
2. 在测试中添加 `print()` 语句
3. 使用调试器单步执行测试
4. 检查Mock对象的调用记录

## 未来改进

1. **性能测试**：添加数据库操作性能测试
2. **集成测试**：添加真实数据库环境的集成测试
3. **覆盖率报告**：生成代码覆盖率报告
4. **并发测试**：添加多线程环境下的测试用例