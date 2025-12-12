# 汉语国学爬虫（词语 & 成语）

本仓库包含面向“成语（chengyu）”和“词语（ciyu）”两套并行的爬取工具。两套工具在抓取调度、断点续爬、pending 管理、后台批量写入与指标记录等行为上已统一对齐；页面解析逻辑（extract_*.py）保留各自领域的实现，不随调度层变动。

本文档概述项目功能、运行方式与关键实现点（不修改代码即可复现）。

## 目录概览

- `chengyu/`：成语相关代码

  - `batch_crawl.py`：成语批量爬取主程序（断点续爬、pending、后台写入、性能指标）
  - `extract_chengyu.py`：成语页面的 URL 获取与 HTML 解析（只做解析）
  - `chengyu_mysql.py`：成语写库逻辑（含 TEST_MODE）
- `ciyu/`：词语相关代码（已与 `chengyu` 的调度/写库/指标逻辑对齐）

  - `batch_crawl.py`：词语批量爬取主程序（与成语版行为一致）
  - `extract_ciyu.py`：词语页面的 URL 获取与 HTML 解析（只做解析）
  - `ciyu_mysql.py`：词语写库逻辑（含 TEST_MODE）
- `hanzi/`：若干汉字相关的解析脚本（独立模块）
- `clear_crawled_data.py`：清理已爬取数据的脚本
- `requirements.txt`：依赖列表

## 主要功能（实现要点）

1. 断点续爬（resume）

   - 每次批次结束会向 `batch_metrics.csv` 追加一行指标记录，包含 `end` 字段表示已成功完成的最后序号。
   - 启动时会读取 `batch_metrics.csv` 的最大 `end` 值作为下一次 `start_index`，实现逐批次断点续爬。
   - 如果上一次在某批次中途中断（Ctrl+C），该批次不会把指标写入 CSV，因此下次运行会从该批次的起点重新执行（不会跳过尚未完成的成批任务）。
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

   - 对于检测到 `blocked` 或常见限流状态码（429、403、503），统一使用指数退避重试：从 `RETRY_BACKOFF_BASE` 开始、每次翻倍、直到 `RETRY_BACKOFF_MAX` 为止，达到最大退避后会停止重试，并通过 `NetworkOutageError` 等外部捕获上报。
6. 指标与错误输出

   - 每批会输出并追加到 `batch_metrics.csv` 的字段：
     - `batch_idx`, `start`, `end`, `processed`, `success`, `fail`, `missing_detail_pages`, `elapsed_seconds`, `insert_rate_per_sec`, `error_rate`, `timestamp`。
   - 若有解析或写入错误，会写入 `batch_{idx}_errors.csv`，格式为 `(key, error)`，便于审查。
7. 页面解析与职责分离

   - 所有 HTML 解析/URL 获取逻辑集中在 `extract_chengyu.py` 与 `extract_ciyu.py`。
   - 批次控制、断点、pending、写入、指标等调度逻辑集中在各自的 `batch_crawl.py`，便于维护与对齐。

## 运行说明

1. 安装依赖：

```powershell
pip install -r requirements.txt
```

2. 配置（可在文件顶部调整）

   - `chengyu/batch_crawl.py` 与 `ciyu/batch_crawl.py` 顶部定义了默认常量：`DEFAULT_BATCH_SIZE`、`DEFAULT_REQUEST_DELAY`、`DEFAULT_SEARCH_DELAY`、`DEFAULT_JITTER_MAX` 等，可根据需要在运行前修改。
   - 数据库连接与 TEST_MODE 在 `chengyu/chengyu_mysql.py` 和 `ciyu/ciyu_mysql.py` 中配置。若想仅打印不写库，请将 `TEST_MODE = True`。
3. 启动爬取（示例）：

```powershell
# 成语
python chengyu/batch_crawl.py
# 或者使用 uv (如你本地使用 uv 工具)
uv run .\\chengyu\\batch_crawl.py

# 词语
python ciyu/batch_crawl.py
uv run .\\ciyu\\batch_crawl.py
```

4. 断点恢复：
   - 在中断（Ctrl+C）后，脚本会优雅等待写线程完成短时间写库并退出；下次再运行会从 `batch_metrics.csv` 的最大 `end` 继续处理（并首先清理 `pending.json` 中的未确认条目）。

## 指标解释（关键字段）

- `processed`：本次批次中已尝试并判定结果（成功或失败）的条目数（包含解析失败但被计为已处理的项）。
- `success`：成功入队并由写线程尝试入库的条目数（写成功以 `writer_stats` 为准，脚本不再重复叠加统计）。
- `fail`：抓取/解析或写库失败的条目总数（包含写线程统计的失败）。
- `missing_detail_pages`：在搜索阶段未能定位到详情页（`get_*_url` 返回 None）的条目数量。

若发现 `success` 与 `processed` 差异较大，可查看对应的 `batch_{idx}_errors.csv` 了解具体失败原因。

## 开发与调试建议

- 本地测试时建议开启 MySQL 的 `TEST_MODE`（`ciyu/ciyu_mysql.py` 或 `chengyu/chengyu_mysql.py`）以避免误写真实数据库。测试模式将打印 SQL 与关系计划。
- 若需要增加更多指标（如 `failed_extracts`、`pending_retries`），建议在相应 `batch_crawl.py` 中新增计数并写入 `metrics`。
- 若要进一步统一或抽取通用代码（例如共有的 `pending`/`writer` 实现），可考虑将公共逻辑提取到 `common/` 工具模块。

## 注意事项与风险

- 本脚本会对第三方网站发起真实请求，请确保遵守目标网站的 robots/使用条款及本地网络策略。
- 长时间运行可能触发目标站点的限流或封禁，请合理设置 `request_delay`、`jitter_max` 及重试策略。
- 在生产环境运行前务必配置好数据库连接与备份策略，测试模式不会写库但也无法验证后端事务行为。
- 如果遇到临时断网（`requests.RequestException`），会以 `RETRY_BACKOFF_BASE`（默认 5 分钟）为起点逐次翻倍等待、退避时间不会超过 `RETRY_BACKOFF_MAX`；一旦已经等待过最大退避仍然无法恢复，脚本会抛出 `NetworkOutageError` 终止当前批次，提示等待网络恢复后再重启。
