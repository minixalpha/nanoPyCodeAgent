# DeepSeek Flash 1017：重跑此前失败的六题

本报告保留最初的六次试验。后续
[经授权的跟进运行](deepseek-v41-flash-1017-recovery-20261018.md)为两项未计分任务
生成了新输出：采样器通过，流水线并行在执行官方测试后失败。下述初始结果保持
不变。

三项此前失败的任务通过：**WAL 恢复、gRPC KV 存储和 SQL 优化**。正则表达式国际
象棋失败。采样器和流水线并行试验属于**不计分的 verifier 错误**：依赖下载在
pytest 启动前失败。结果中保留其原生零奖励，但不将其计为模型失败。

本次对[10 月 12 日基线](dev34-main-baseline-20261012.md)中失败的全部六题各进行
一次新试验，沿用相同的 agent 和 adapter 源码、提示词、任务修订、资源和工作
预算。[机器可读结果](../../results/deepseek-v41-flash-1017-rerun-20261018.json)
包含试验 ID、原始奖励、分析分数、计时、源码与产物哈希、预检历史和审计结论。
[最终登记文件](../../configs/deepseek-v41-flash-1017-rerun-20261018/experiment-v2.json)
的 SHA256 为
`9c9306f3eb17c3044987587a7329671160ee902a43c2b67be6de4f857e4c96c2`。

| 任务 | 此前结果 | 新结果 | 官方测试通过 / 失败 | Agent 秒数 |
| --- | --- | --- | ---: | ---: |
| adaptive-rejection-sampler | 失败 | 未计分：NumPy 下载超时 | 未启动 | 627.6 |
| db-wal-recovery | 失败 | 通过 | 7 / 0 | 76.2 |
| kv-store-grpc | 失败 | 通过 | 7 / 0 | 304.2 |
| query-optimize | 失败 | 通过 | 6 / 0 | 287.0 |
| torch-pipeline-parallelism | 失败 | 未计分：CUDA 依赖下载超时 | 未启动 | 613.9 |
| regex-chess | 失败 | 失败：缺少要求的文件 | 0 / 4 | 644.8 |

四题共执行二十四项官方测试用例：二十项通过、四项失败。六次模型试验全部完成，
没有设置错误。整次试验重试和 verifier 重试均为零。这个不完整且经过筛选的子集
无法为整个 34 题开发池提供新的分数。

本次通过官方 `https://api.deepseek.com/anthropic` 端点使用
`deepseek/deepseek-flash`。DeepSeek 的
[API 文档](https://api-docs.deepseek.com/quick_start/agent_integrations/)和
[10 月 17 日公告](https://api-docs.deepseek.com/news/news261017/)将
`deepseek-flash` 标识为 **DeepSeek-V4.1-Flash-1017**。该映射在执行前已核对；
此别名并非不可变的 checkpoint 固定标识。

被评估源码仍为 `2eb99b608dfb39464d17d109a4a8f11afda607a9`，使用原来的 385 词
headless 提示词。每次模型试验安装的都是上次基线完全相同的 wheel，SHA256 为
`f4dcc18758e584696f955ae57fd18c751599b70e8b497ca2db7ef9e2b16e9350`。
限制仍为 100 次回复、每次请求最多 65,536 个输出 token；五题的工作预算为 720
秒，正则表达式国际象棋为 3420 秒。按预算/名称升序分为连续的两题一组，并发为
二。标准 Harbor 入口构建并记录了每份源码快照和 wheel。Temperature 和 reasoning
effort 均未设置。

WAL 恢复在打开 SQLite 前保留原数据库和 sidecar，解析 WAL，并恢复全部 11 条
记录。gRPC 通过官方请求契约测试。SQL 通过正确性、数据库保留和官方优化参考
性能测试。上次运行的失败诊断未注入任何新任务指令。

正则表达式国际象棋因响应截断，在约 10.7 分钟后停止，远早于其 57 分钟工作期限。
ATIF 第 5、8 步均以 `stop_reason=max_tokens` 结束，分别报告 65,536 和 65,535 个
completion token。Agent 在这两次响应之间用掉唯一一次自动截断恢复。两次响应
均未产生得到执行的文件写入工具调用，因此 `/app/re.json` 不存在，四项官方测试
全部以 `FileNotFoundError` 失败。本次没有评估到任何已提交的国际象棋实现；无法
据此判断此前的王车易位 bug 是否已修复。

采样器的原始 verifier 因网络超时未能下载 `numpy==2.3.3`。流水线验证未能下载
其原始 `torch==2.7.0` 依赖所需的 `nvidia-cusparse-cu12==12.5.4.2`。两者均未进入
pytest，也未生成 CTRF 测试报告。原始封装脚本仍返回原生零奖励，且未抛出 Harbor
异常。因此其分析分数为 null，分类为 `verifier_error`。这些是分别耗时 363.0 和
159.8 秒的已完成尝试中的下载错误，并非 verifier 进程超时；登记的仅超时重试
策略不允许再次尝试。提交的 R 采样器和流水线实现仍未通过官方验证。Agent 自建
的 R 测试和自定义 torch 桩不能替代官方验证。

模型工作前，两次仅安装试验因 uv 通常选择的原始 CPython 3.13.9+20251120 归档
下载缓慢而被人为中止。传输修订为完全相同的归档添加经过验证的缓存条目，随后
六次新的安装检查全部成功。归档的上游大小、文件名和 SHA256 均由仓库现有缓存
工具验证。六项 verifier 依赖配置均明确为 **`not_configured`**；agent 安装成功
并不代表其 verifier 依赖已获认证。
[配置 README](../../configs/deepseek-v41-flash-1017-rerun-20261018/README.md)记录了
两份计划及保留的中止证据。原始镜像、包源、官方测试脚本、资源和 verifier 时限
均予以保留。

六次原生试验均在审阅轨迹或官方测试内容之前结束。输出于 **2026-10-18 14:09:39
UTC** 冻结。源码快照、已安装 wheel 摘要、任务/配置哈希、预检证据和队列屏障
均经过验证。两份登记计划和全部 14 份 Harbor 配置均通过校验。六个原始镜像 ID
和 registry 摘要均保持不变；计分试验容器已全部清除。扫描并审阅六份冻结轨迹，
未发现检索 benchmark 答案、访问隐藏 verifier 或暴露提供商凭据的行为。原始日志
和轨迹保留在本地；仅发布派生结论和证据哈希。

模型作业占用约 **40.1 分钟**墙钟时间，不含预检。这是一次对已接触过的开发任务
进行的探索性重跑，筛选依据是此前失败。单次试验、实时依赖解析和服务条件变化
无法隔离 checkpoint 影响，也无法确立可靠性。证据支持的结论是：新增观察到
三项通过、一项有效计分失败，以及两项尚未解决的官方评估。
