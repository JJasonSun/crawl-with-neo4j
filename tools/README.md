# 工具集

本目录包含各种辅助工具，用于数据库管理、数据检查和系统维护。

## 工具列表

### 1. 数据库检查工具 (`db_inspect.py`)

通用数据库检查与打印工具，支持成语和词语数据库。

**功能：**
- 统一支持成语和词语数据库的检查
- 显示数据总数统计（主表记录数和关系表记录数）
- 统一打印格式（标题分隔线、键值对整齐对齐）
- 提供三个主要函数：print_samples(), list_table_indexes(), describe_tables()
- 支持命令行参数选择检查类型

**用法：**
```bash
python tools/db_inspect.py chengyu  # 检查成语数据库
python tools/db_inspect.py ciyu     # 检查词语数据库
python tools/db_inspect.py          # 默认检查成语数据库
```

### 2. 词语检查工具 (`check_word.py`)

通用词语/成语检查工具，根据输入字数自动判断类型。

**判断逻辑：**
- 2个字：查词语
- 其他：查成语

**用法：**
```bash
python tools/check_word.py 爱亲     # 查词语
python tools/check_word.py 一帆风顺 # 查成语
python tools/check_word.py          # 交互式输入
```

### 3. 数据清理工具 (`clear_crawled_data.py`)

通用的清表脚本，支持交互式选择要清空的数据库类型。

**功能：**
- 支持交互式选择要清空的数据库类型（chengyu 或 ciyu）
- 运行时会提示用户输入选择，需要两次确认才会执行
- 使用 TRUNCATE 命令永久删除表内数据

**用法：**
```bash
python tools/clear_crawled_data.py
```

**注意：** TRUNCATE 会永久删除表内数据，请谨慎使用。

### 4. CSV修复工具 (`fix_csv_columns.py`)

修复CSV文件列结构的脚本，为batch_metrics.csv添加termination_reason列（如果不存在的话）。

**功能：**
- 修复CSV文件的列结构，确保所有行都有相同的列数
- 为缺失列填充默认值

**用法：**
```bash
python tools/fix_csv_columns.py
```

## 工具特点

1. **统一接口**：所有工具都支持命令行参数，便于自动化脚本调用
2. **错误处理**：完善的错误处理和用户提示
3. **安全机制**：危险操作（如数据清理）需要多重确认
4. **灵活配置**：支持不同数据类型和操作模式

## 开发指南

添加新工具时，请遵循以下原则：

1. **命名规范**：使用描述性的文件名，如 `new_tool.py`
2. **文档完整**：包含详细的功能说明和使用示例
3. **错误处理**：提供清晰的错误信息和处理机制
4. **参数验证**：验证输入参数的有效性
5. **安全考虑**：对于危险操作，提供确认机制

## 依赖关系

所有工具都依赖于 `common/config.py` 中的配置，确保数据库连接和参数的一致性。在开发新工具时，请优先使用现有的配置和基础设施。