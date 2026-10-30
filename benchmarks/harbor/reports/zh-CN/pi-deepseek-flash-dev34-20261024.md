# Pi + DeepSeek Flash：34 题开发集 baseline

**34 题均获得一次全新的模型尝试**，并于 2026 年 10 月 29 日运行结束。
审计结果为 **26 题官方验证通过、6 题评分失败、2 次旧适配器超时尝试不评分**。
26 次通过中，一次发生在 agent 达到时限且确认停止之后，另一次读取过公开参考测试
和解法。因此，本轮**不能给出完整且无答案接触的 34 题通过率**。

未修改的标准摘要记录了 25 次正常通过、6 次正常失败和 3 次
`AgentTimeoutError` 执行错误。原生 reward 为 26 个一和 8 个零。
审计采纳有进程托管确认的 Caffe 超时尝试的原始一分，将两次旧超时的原始零分
在分析中保留为空。审计不改写异常、不修改原始 reward，也不替换模型输出。

[审计结果 JSON](../../results/pi-deepseek-flash-dev34-20261024.json) 包含全部
trial ID、源码/任务/配置来源、原始及分析结论、官方测试数量、用量、时间、
审计标记和证据哈希。[v7 登记](../../configs/pi-deepseek-flash-dev34-20261024/experiment-v7.json) 保留前六次尝试，
并为剩余 28 题登记修正后的进程托管。全部输出于
**2026-10-30 13:54:30.827662 UTC** 完成哈希冻结，早于新的解题轨迹或隐藏测试
内容审阅；[冻结清单](../../configs/pi-deepseek-flash-dev34-20261024/outputs-freeze.json) 覆盖 **1,449 个文件**。

## Agent、模型与协议

| 属性 | 值 |
| --- | --- |
| 题池 | 与 10 月 12 日完全相同的开发集选择：34 题，任务 revision 一致；其余 55 个任务包未打开 |
| Agent | 未修改的上游 Pi 1.4.0 本地二进制分发包；固定所有文件和权限；未独立核验上游发布压缩包校验和 |
| 模型 | `deepseek/deepseek-flash`，官方 `https://api.deepseek.com` OpenAI 兼容端点 |
| 别名 | 10 月 24 日和 27 日核对的官方文档映射为 DeepSeek-V4.1-Flash-1017；别名可变，不是不可变 checkpoint |
| 推理和采样 | `high`；未设置 temperature |
| Agent 行为 | 原生 prompt、工具、上下文压缩和请求重试；不复制个人设置、扩展、技能、历史及其他 provider |
| 模型元数据 | 上下文 1,000,000；输出上限 384,000；保留 Pi 原生生成行为 |
| 限制 | 保留任务原生 agent 时限及资源；独立的 1,800 秒安装时限 |
| 队列 | 按原生时限再按名称升序；相邻两题设屏障；并发二；每题一个输出 |
| Verifier | 原始官方脚本和单次时限；只有 verifier 超时可对同一输出重试，最多三次；实际重试零次 |
| 安装 | 原始 34 次检查通过；进程托管修正后额外 28 次检查/探针通过 |

QEMU 已登记的 `qemu-alpine-ssh-v1` 依赖 profile 在两个源码版本下均通过。
其余 33 题的 profile 明确保留为 `not_configured`；安装成功不等于未支持的
verifier 依赖通过预检。经核验的缓存保留原始包名、大小、SHA256、来源及任务
镜像。每批启动前核验原始镜像身份和 repository digest。仅在不强制删除的前提下
清理本轮新增镜像引用；受保护镜像和九个更早的停止态恢复容器全部保留。

```text
plan SHA256: d90107ed15e47981fb3a09e74eb5d3b0e4f72acc96b30308c6d66ec28151128c
freeze SHA256: 76b775d898bbb84b21f80eee1061806d7d949465f9eef60dcab6dedeb326734b
results SHA256: b85d3bf2b0ea9661940f0e6b08e3bea71b2c41ae34da5c89f9ecd5197c6c8ff5
selection SHA256: 4572b1cc432a16b9c5d1dd554c8d2189ae80414f386a90bf03829bc4d0c3da85
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
first six adapter source: d6ed70a5d6a1c5b0f9b6c9d20b4a1c2b49153f67
remaining 28 adapter source: 29db8d7abbbe5f1660b8fb4d7caeeb0d183dc64d
```

此前 Nano baseline 使用 100 次回复、65,536 token 的输出请求、原生时限减
180 秒的工作预算、Anthropic 兼容端点，且未设置 reasoning effort。
Pi 使用原生循环、完整任务时限、OpenAI 兼容端点及 `high` 推理。
日期、可变模型别名和这些协议差异使本轮无法进行 agent 质量或 checkpoint
效果的因果比较。各题之间未优化 agent 或 prompt。

## 进程托管修正与超时记账

前六次尝试使用 `d6ed70a`，三题正常通过，一题正常失败；
`adaptive-rejection-sampler` 和 `db-wal-recovery` 超时。运行元数据时间戳显示
sampler 在 verifier 运行期间仍有 Pi 活动，因此控制器在整对任务结束后、
第七题开始前停止。通过 **225 项 Harbor 测试**、禁网 Docker 取消探针及
28 次全新安装/托管检查后，尚未启动的 28 题改用 `29db8d7`。
Pi 字节、模型设置、prompt/工具、任务顺序/revision 和预算均未改变。
参见[配置历史](../../configs/pi-deepseek-flash-dev34-20261024/README.md)、
[原始六次尝试证据](../../configs/pi-deepseek-flash-dev34-20261024/model-prefix-evidence.json)、
[超时证据](../../configs/pi-deepseek-flash-dev34-20261024/timeout-boundary-evidence.json) 和
[Docker 探针](../../configs/pi-deepseek-flash-dev34-20261024/process-supervision-probe-evidence.json)。

- **Sampler：** 在所记录的 agent 结束时间后仍有 40 条消息元数据记录，
  部分与评分重叠。Verifier 还遇到了 APT 锁和 `scipy==1.16.2` 下载超时，
  官方 pytest 未开始。原始零分同时具有冻结边界无效和 verifier 依赖错误。
- **WAL recovery：** 未观察到结束后的消息，但旧适配器从未确认进程已停止。
  官方测试报告缺少 `/app/recovered.json`（0 项通过、7 项失败）。由于超时
  边界未确认，原始零分仍不评分。
- **Caffe：** 修正后的适配器达到原生 3,600 秒 agent 时限后，确认取消并
  **停止了 13 个进程**，随后运行官方 verifier，**六项测试全部通过**。
  原生 `AgentTimeoutError` 和标准 `execution_error` 摘要保留；分析分数为一。
  未记录到 agent 结束后或 verifier 启动后的消息。

修正源码下全部 28 次尝试在官方评分前均有正常完成或已确认取消的托管记录。
强制检查会拒绝缺失或不完整记录。正常完成时允许有意启动的解题服务继续运行；
取消时会同时停止脱离原会话的 agent 工具。修正不能追溯验证前两次超时尝试。
**模型阶段安装错误零次、整题重试零次、verifier 重试零次**。
Sampler 的依赖错误与其无效边界排除项重叠，不构成第三个不评分任务。

## 逐题结果

| 任务 | 此前 Nano 原始分数 | Pi 原始分数 | 审计结论 | 官方测试通过 / 失败 | Agent 秒数 |
| --- | ---: | ---: | --- | ---: | ---: |
| adaptive-rejection-sampler | 0 | 0 | 不评分：边界无效及 verifier 错误 | 未开始 | 901.3 |
| build-cython-ext | 1 | 1 | 通过 | 11 / 0 | 834.2 |
| cancel-async-tasks | 1 | 0 | 失败 | 5 / 1 | 104.8 |
| cobol-modernization | 1 | 1 | 通过 | 3 / 0 | 430.2 |
| db-wal-recovery | 0 | 0 | 不评分：超时边界未确认 | 0 / 7 | 898.7 |
| fix-code-vulnerability | 1 | 1 | 通过 | 6 / 0 | 28.2 |
| git-multibranch | 1 | 1 | 通过 | 1 / 0 | 80.5 |
| kv-store-grpc | 0 | 1 | 通过 | 7 / 0 | 36.1 |
| log-summary-date-ranges | 1 | 0 | 失败 | 1 / 1 | 13.9 |
| merge-diff-arc-agi-task | 1 | 1 | 通过 | 5 / 0 | 77.1 |
| model-extraction-relu-logits | 1 | 0 | 失败 | 0 / 1 | 177.0 |
| multi-source-data-merger | 1 | 1 | 通过 | 3 / 0 | 34.3 |
| nginx-request-logging | 1 | 1 | 通过 | 8 / 0 | 52.1 |
| openssl-selfsigned-cert | 1 | 1 | 通过 | 6 / 0 | 16.5 |
| pypi-server | 1 | 1 | 通过 | 1 / 0 | 70.3 |
| pytorch-model-cli | 1 | 0 | 失败 | 5 / 1 | 660.7 |
| pytorch-model-recovery | 1 | 1 | 通过 | 5 / 0 | 178.3 |
| qemu-alpine-ssh | 1 | 1 | 通过 | 1 / 0 | 654.9 |
| query-optimize | 0 | 0 | 失败 | 5 / 1 | 318.0 |
| regex-log | 1 | 1 | 通过 | 1 / 0 | 157.0 |
| torch-pipeline-parallelism † | 0 | 1 | 通过 | 4 / 0 | 562.2 |
| torch-tensor-parallelism | 1 | 1 | 通过 | 13 / 0 | 90.8 |
| write-compressor | 1 | 1 | 通过 | 3 / 0 | 304.1 |
| constraints-scheduling | 1 | 1 | 通过 | 3 / 0 | 23.0 |
| custom-memory-heap-crash | 1 | 1 | 通过 | 6 / 0 | 96.2 |
| dna-assembly | 1 | 0 | 失败 | 0 / 1 | 763.3 |
| llm-inference-batching-scheduler | 1 | 1 | 通过 | 6 / 0 | 337.7 |
| path-tracing | 1 | 1 | 通过 | 5 / 0 | 133.1 |
| schemelike-metacircular-eval | 1 | 1 | 通过 | 1 / 0 | 800.1 |
| caffe-cifar-10 | 1 | 1 | 超时，确认停止后通过 | 6 / 0 | 3600.4 |
| circuit-fibsqrt | 1 | 1 | 通过 | 3 / 0 | 239.0 |
| mteb-leaderboard | 1 | 1 | 通过 | 2 / 0 | 667.7 |
| regex-chess | 0 | 1 | 通过 | 4 / 0 | 1618.2 |
| build-pov-ray | 1 | 1 | 通过 | 3 / 0 | 267.4 |

† `torch-pipeline-parallelism` 读取过公开 Terminal-Bench 测试和参考解法；
保留其官方通过结果，并在下文标记。测试数量取最后一条官方 pytest 汇总，
保留参数化实例：pipeline 为四项、tensor parallelism 为 13 项；原生 CTRF
分别去重为三项。32 个采纳的评测执行了 **139 项官方测试：133 项通过、
6 项失败、错误/跳过均为零**。不评分的 WAL 尝试另有七项失败。
嵌套的上游测试或自测数量不叠加进最终官方包装测试总数。

六个有效失败的证据如下：

| 任务 | 官方失败证据 |
| --- | --- |
| cancel-async-tasks | 超额任务缺少清理消息：应为 2 次，实际 0 次 |
| log-summary-date-ranges | 月初至今 ERROR 数量应为 4682，实际 14160 |
| model-extraction-relu-logits | 恢复矩阵的第 24 行未匹配 |
| pytorch-model-cli | CLI 预测值与预期不同 |
| query-optimize | 耗时 0.8657636019925121 秒，超过 1.05 × 0.6539265539904591 秒 |
| dna-assembly | 引物熔解温度差 5.4112089999999995 摄氏度，超过 5 度限制 |

这些是官方断言结果，不是完整根因的证明。相对于
[10 月 12 日 Nano baseline](dev34-main-baseline-20261012.md)，三题从失败变为
官方通过：`kv-store-grpc`、`torch-pipeline-parallelism`（标记答案接触）和
`regex-chess`。五题从通过变为失败：`cancel-async-tasks`、
`log-summary-date-ranges`、`model-extraction-relu-logits`、`pytorch-model-cli`
和 `dna-assembly`。Sampler 和 WAL 仍未解决。此前 Nano 的 28/34 无法与
完整的新 Pi 通过率直接比较，因为本轮没有提供后者。

## 答案接触与私有产物

冻结后，针对性扫描审阅了 **925 次记录到的工具启动**及匹配输出，检查 benchmark
仓库、隐藏路径和环境变量访问。`torch-pipeline-parallelism` 从公开仓库
`harbor-framework/terminal-bench-2` 下载了上游 `tests/test_outputs.py`
（178 行）、`solution/solve.sh`（112 行）和 `instruction.md`（33 行），
读取参考解法并执行下载的测试。远端 `main` 未固定到登记的任务包 revision。
这次通过不代表独立解题。WAL 和 Git 曾列出当时为空的 `/logs/verifier`；
这些目录列表输出未包含官方测试。MTEB 题访问过其应用上游源码、公开结果和
Scandinavian leaderboard，这与 Terminal-Bench 参考材料单独记录。

WAL 和 `llm-inference-batching-scheduler` 打印的环境变量包含配置中的
DeepSeek API key。精确匹配扫描在这两题的事件文件及原生会话文件中，共发现
**四个含 key 的本地原始文件**。不发布 key 值或原始轨迹；下一轮实验前应
轮换该 key。公开产物只包含分析结论及哈希。这种针对性审计不能证明所有其他
答案接触或数据外传途径都不存在。该题池本身也是此前已接触的开发材料。

## 时间、用量与复现

模型任务从 **2026-10-29 13:54:04.318461 UTC** 运行到
**2026-10-29 19:11:52.019151 UTC**，共 **317.8 分钟**，包含成对屏障、
评分和进程托管修正期间的间隔。Agent 执行累计 **15,227.44641 秒**。
全部控制器和任务容器均已退出；更早的停止态恢复容器保留。

记录的用量合计 **27,164,763 输入 token**（含 **26,331,264 缓存 token**）
和 **718,414 输出 token**。按登记峰值费率估算的已知费用小计约
**$1.270134084**。三次中断尝试的用量和费用均不完整；旧适配器错误的完整性
标记原样保留，仅在派生审计字段中纠正。进行中的请求或旧超时后继续发生的活动
可能缺失。这些是已知小计，不是完整 token 总数或对账后的账单；登记价格也未
包含非高峰折扣。

登记控制器从实验 worktree 根目录启动，key 仅通过环境变量提供。
它在各自冻结的源码 checkout 中调用标准 Harbor 入口：

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/harbor-supervised-runtime-venv"
uv run --frozen --project jobs/supervised-source/benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev34-20261024/experiment-v7.json \
  --phase all
```

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>
```

已完成记录会跳过；已开始但未完成的记录拒绝重放。最终 v7 计划验证通过，
34 份源码快照、任务 revision、公开模型配置和分发包固定值全部匹配，
成对屏障和安装门禁均通过。审计重新核验了全部 1,449 个冻结文件的哈希。
原生产物保存在忽略的 `jobs/runtime-source/jobs/` 和
`jobs/supervised-source/jobs/` 下；报告和审计 JSON 构成可分享的 baseline 记录。
完整英文与简体中文报告在同一变更中维护。

## 运行后的工作流评审

本轮结束后修正了四个可复现的工作流缺陷：模型加载警告即使返回零退出码也可能
掩盖配置回退；多个 Pi 配置可能覆盖同一任务的快照；失败流初始化的零用量在
重试成功后可能被标为完整；共享分发包首次并发发布可能使一次准备中止。
回归测试在本轮评测使用的修正源码上复现了九个失败，更新后的完整 Harbor
测试集 **238 项通过**。固定的 Pi 1.4.0 离线探针接受了已登记配置，并在不调用
模型的情况下，拒绝了虽然退出码为零、但 `maxTokens` 无效的配置。

[评审证据](../../configs/pi-deepseek-flash-dev34-20261024/review-fixes-evidence.json)
记录了修复和归档检查。每个归档模型任务只有一个 Pi agent，使用已登记的有效
公开模型配置；在检查的任务日志/事件中未发现模型加载警告或失败的零用量
assistant 事件。全部 1,449 个冻结文件哈希仍匹配。原始评测源码、异常、用量、
结论和结果 JSON 均保持不变；这些工作流修复用于后续运行，不表示重新运行过
这份 baseline。
