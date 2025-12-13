# 汉语国学爬虫（词语 & 成语）

成语（chengyu）与词语（ciyu）爬虫已完成调度层统一：公共逻辑集中在 `common/`，领域差异仅保留在 `extract_*.py`（URL 发现、HTML 解析、建表/写库）。

推荐入口：**直接运行各自的 `extract_*.py`**，底层自动调用通用调度器。

## 目录概览

- `common/`：核心调度与基础设施
   - `crawl_runner.py`：通用批量爬取调度器，处理断点续爬、pending、后台写库、指标与错误输出
   - `retry_runner.py`：通用错误重试调度，读取错误文件并重新处理
   - `config.py`：集中化配置管理，包含数据库连接和爬虫参数
   - `base_db.py`：数据库操作抽象基类，消除代码重复
   - `exceptions.py`：自定义异常体系，提供结构化错误处理
   - `logger.py`：结构化日志系统，支持JSON格式和日志轮转
- `tools/`：辅助工具集
   - `db_inspect.py`：数据库检查工具，支持成语和词语数据检查
   - `check_word.py`：词语检查工具，智能识别成语或词语
   - `test_connections.py`：数据库连接测试工具
   - `clear_crawled_data.py`：清理已爬取数据的脚本
   - `fix_csv_columns.py`：修复CSV文件列结构的脚本
- `chengyu/`：成语领域代码
   - `extract_chengyu.py`：成语 URL & HTML 解析 + 领域配置入口（运行它即可启动成语爬取）
   - `chengyu_DB.py`：成语数据库操作类（ChengyuDB），继承自BaseDB，统一管理 MySQL 写入和 Neo4j 查询
- `ciyu/`：词语领域代码
   - `extract_ciyu.py`：词语 URL & HTML 解析 + 领域配置入口（运行它即可启动词语爬取）
   - `ciyu_DB.py`：词语数据库操作类（CiyuDB），继承自BaseDB，统一管理 MySQL 写入和 Neo4j 查询
- `hanzi/`：汉字相关的解析脚本（独立，不在本次重构范围）
- `tests/`：测试框架
   - `test_database.py`：数据库操作测试
   - `test_config.py`：配置系统测试
   - `test_logger.py`：日志系统测试
   - `test_exceptions.py`：异常处理测试
   - `run_tests.py`：测试运行器
- `requirements.txt`：依赖列表

## 主要功能（实现要点）

1. 断点续爬（resume）

   - 通用调度器读取 `batch_metrics.csv` 最大 `end` 续跑；首次会自动创建表头，旧文件缺列会自动补齐（含 `termination_reason`）。
   - 若上次在批次内中断（Ctrl+C），未写入指标的批次会整体重跑，不会跳过未完成的条目。
2. pending 管理与幂等写入

   - 爬取过程中解析到的数据会先入队，后台写线程按批写入数据库。
   - 在入库前将主词写入 `pending.json`（用于记录尚未确认写入的词条），写入成功后从 `pending.json` 中移除。
   - 这样即使中断，下次运行会先处理 `pending.json` 中未完成的项，保证数据一致性与幂等性。
3. 后台批量写入

   - 采用生产者-消费者模型：主线程抓取并把解析结果放入队列，单独的写线程负责批量写入数据库（`DB_BATCH_SIZE`、`DB_FLUSH_INTERVAL` 控制刷新频度）。
   - 写线程会维护 `writer_stats`（成功/失败计数），写失败会记录到错误日志文件。
4. 抖动与固定延迟

   - 每次请求前会有两层延迟控制：固定延迟（`request_delay` / `search_delay`）+ 随机抖动（`jitter_max`）。固定延迟保证最小间隔，抖动用于打散请求节奏，降低被限流概率。
5. 限流/封禁检测与退避

   - 对于检测到 `blocked` 或常见限流状态码（429、403、503），统一使用指数退避：`retry_backoff_base` 起步、每次翻倍、直至 `retry_backoff_max`，超限后中止当前批次。
6. 指标与错误输出

   - 追加字段（含新增 `termination_reason`）：`batch_idx`, `start`, `end`, `processed`, `success`, `fail`, `missing_detail_pages`, `termination_reason`, `elapsed_seconds`, `insert_rate_per_sec`, `error_rate`, `timestamp`。
   - `termination_reason` 取值：`manual_exit`（Ctrl+C）、`network_outage`（退避到上限仍失败）、`blocked_ip`（本批无新增）、`batch_completed`（正常结束但非全量）、`all_done`（最后批完成）。
   - 错误文件：`batch_{idx}_errors.csv`，表头为领域主键与 `error`。
7. 页面解析与职责分离

   - URL/HTML 解析留在各自 `extract_*.py`；调度、pending、写库、指标由 `common/crawl_runner.py` 统一处理。
8. 配置集中化

   - 所有数据库配置（MySQL、Neo4j）和全局参数集中在 `common/config.py`，各模块通过导入使用，避免重复配置。
   - 支持测试模式（TEST_MODE）和默认参数统一管理。
   - 所有配置参数都有详细注释，说明用途和推荐值。
9. 通用数据库检查工具

   - `tools/db_inspect.py` 统一支持成语和词语数据库的检查、索引查看和表结构描述。
   - 显示最后5个记录，便于查看最新爬取的数据。
   - 使用方法：`python tools/db_inspect.py chengyu` 或 `python tools/db_inspect.py ciyu`
10. 通用词语检查工具

   - `tools/check_word.py` 支持查询成语和词语，根据字数自动判断类型。
   - 判断逻辑：2个字查词语，其他字数都查成语。
   - 使用方法：`python tools/check_word.py 爱亲`（查词语）、`python tools/check_word.py 一帆风顺`（查成语）
   - 交互式模式：`python tools/check_word.py`（无参数时进入交互模式）
11. 数据库连接测试工具

   - `tools/test_connections.py` 统一测试 MySQL 和 Neo4j 数据库连接。
   - 使用方法：`python tools/test_connections.py`（测试所有）、`python tools/test_connections.py mysql`（只测试MySQL）、`python tools/test_connections.py neo4j`（只测试Neo4j）
   - 测试功能已集成到 `common/config.py` 中，各数据库模块统一使用。
12. 统一数据库操作类

   - `chengyu/chengyu_DB.py`：成语数据库操作类（ChengyuDB），继承自BaseDB，统一管理 MySQL 写入和 Neo4j 查询
   - `ciyu/ciyu_DB.py`：词语数据库操作类（CiyuDB），继承自BaseDB，统一管理 MySQL 写入和 Neo4j 查询
   - 通过抽象基类 `common/base_db.py` 消除代码重复，提高可维护性
   - 支持测试模式，统一错误处理和连接管理
13. 结构化异常处理

   - `common/exceptions.py` 提供自定义异常体系，包括网络异常、解析异常、限流异常、数据库异常等
   - 所有异常都继承自 `CrawlerBaseException`，支持错误码和额外数据
   - 便于错误分类和处理，提高调试效率
14. 结构化日志系统

   - `common/logger.py` 提供结构化日志记录，支持JSON格式和日志轮转
   - 专用日志方法：`crawl_start()`, `crawl_success()`, `crawl_error()`, `db_operation()` 等
   - 支持日志级别控制和额外数据记录，便于分析和调试
15. 测试框架

   - `tests/` 目录包含完整的测试用例，覆盖数据库操作、配置系统、日志系统和异常处理
   - 使用 `tests/run_tests.py` 运行所有测试，或单独运行特定测试模块
   - 测试使用Mock对象模拟外部依赖，确保测试的独立性和可重复性

## 运行说明

1. 安装依赖（推荐 uv）

```powershell
uv pip install -r requirements.txt
```

2. 配置

- 所有配置集中在 `common/config.py`，包括数据库连接参数和爬虫运行参数
- 各领域特定参数（批大小/延迟/抖动/退避）在对应 `extract_*.py` 顶部
- 测试模式通过 `common/config.py` 中的 `TEST_MODE` 控制

3. 启动爬取（推荐入口）

```powershell
# 成语
uv run python chengyu/extract_chengyu.py

# 词语
uv run python ciyu/extract_ciyu.py
```

> 兼容：`chengyu/batch_crawl.py` 与 `ciyu/batch_crawl.py` 仍可运行，内部已委托通用调度。

4. 断点恢复

- 中断后会短暂等待写线程收尾；重启时先处理 `pending.json`，随后从 `batch_metrics.csv` 最大 `end` 继续。

5. 运行测试

```powershell
# 运行所有测试
cd tests
python run_tests.py

# 运行特定测试
python run_tests.py test_database
python run_tests.py test_config
python run_tests.py test_logger
python run_tests.py test_exceptions
```

6. 数据库工具

```powershell
# 测试数据库连接
python tools/test_connections.py

# 检查数据库内容（显示最后5个记录）
python tools/db_inspect.py chengyu
python tools/db_inspect.py ciyu

# 查询词语或成语
python tools/check_word.py 爱亲
python tools/check_word.py 一帆风顺

# 清理已爬取数据
python tools/clear_crawled_data.py

# 修复CSV文件列结构
python tools/fix_csv_columns.py
```

## 指标解释（关键字段）

- `processed`：本次批次中已尝试并判定结果（成功或失败）的条目数（包含解析失败但被计为已处理的项）。
- `success`：成功入队并由写线程尝试入库的条目数（写成功以 `writer_stats` 为准，脚本不再重复叠加统计）。
- `fail`：抓取/解析或写库失败的条目总数（包含写线程统计的失败）。
- `missing_detail_pages`：在搜索阶段未能定位到详情页（`get_*_url` 返回 None）的条目数量。

若发现 `success` 与 `processed` 差异较大，可查看对应的 `batch_{idx}_errors.csv` 了解具体失败原因。

## 开发与调试建议

- 本地测试时建议开启 `common/config.py` 中的 `TEST_MODE` 以避免误写真实数据库。测试模式将打印 SQL 与关系计划。
- 使用结构化日志系统进行调试：日志文件包含详细的执行信息和错误上下文
- 若需要增加更多指标（如 `failed_extracts`、`pending_retries`），建议在相应 `extract_*.py` 中新增计数并写入 `metrics`。
- 新增异常类型时，继承自 `common.exceptions.CrawlerBaseException` 并指定合适的错误码范围
- 数据库操作优先使用 `chengyu_DB.py` 和 `ciyu_DB.py` 中的统一接口，避免直接操作数据库

## 架构优势

1. **代码复用**：通过抽象基类 `BaseDB` 消除了约400行重复代码
2. **错误处理**：结构化异常体系提供清晰的错误分类和处理机制
3. **日志追踪**：结构化日志系统支持JSON格式，便于分析和监控
4. **测试覆盖**：完整的测试框架确保代码质量和功能正确性
5. **配置集中**：所有配置参数集中管理，便于维护和调整
6. **模块化设计**：清晰的职责分离，便于扩展和维护

## 注意事项与风险

- 本脚本会对第三方网站发起真实请求，请确保遵守目标网站的 robots/使用条款及本地网络策略。
- 长时间运行可能触发目标站点的限流或封禁，请合理设置 `request_delay`、`jitter_max` 及重试策略。
- 在生产环境运行前务必配置好数据库连接与备份策略，测试模式不会写库但也无法验证后端事务行为。
- 如果遇到临时断网（`requests.RequestException`），会以 `RETRY_BACKOFF_BASE`（默认 5 分钟）为起点逐次翻倍等待、退避时间不会超过 `RETRY_BACKOFF_MAX`；一旦已经等待过最大退避仍然无法恢复，脚本会抛出 `NetworkOutageError` 终止当前批次，提示等待网络恢复后再重启。
- 日志文件会随时间增长，建议定期清理或配置日志轮转策略
- 测试框架使用Mock对象，可能与真实环境行为存在差异，生产环境部署前应进行充分测试

## 版本历史

- **v2.0**：重构版本，引入抽象基类、结构化异常处理、日志系统和测试框架
- **v1.0**：初始版本，实现基本的爬取和数据库存储功能

## 贡献指南

1. 新增功能时，请遵循现有的模块化设计原则
2. 添加新的异常类型时，请继承自 `CrawlerBaseException` 并使用合适的错误码
3. 数据库操作请优先使用统一的数据库类接口
4. 请为新功能添加相应的测试用例
5. 更新文档时，请保持与代码同步

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。
