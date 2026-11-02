# Pi + DeepSeek Flash：经授权的三题重跑

**三次全新尝试均已结束：两题官方通过、一题计分失败，没有不评分的尝试。
两次通过均接触了公开参考解法和测试，因此都不属于独立解题。** Pipeline
再次发生了上一轮的参考答案接触；WAL 在本次重跑中也访问了参考材料。

维护者要求重跑[原始 34 题 baseline](pi-deepseek-flash-dev34-20261024.md)中
两道不评分的题目，以及接触过参考答案的 pipeline 题。这是根据已有结果选择的
开发集补充实验。原始的 26 次官方通过、六次失败、两次不评分及 pipeline 的
原始答案接触标记均保留；不选取两次尝试中的较好分数，也不将本次补充实验称为
独立 benchmark 或完整、无答案接触的 34 题通过率。

## 协议与准备

[v2 登记](../../configs/pi-deepseek-flash-dev3-rerun-20261102/experiment-v2.json)
保留未修改的 Pi 1.4.0、字节完全一致的公开模型配置、
`deepseek/deepseek-flash`、官方 OpenAI 兼容端点、`high` 推理、未设置的
temperature，以及原生 prompt、工具、上下文压缩和请求重试。模型元数据仍为
1,000,000 token 上下文和 384,000 token 最大输出。可变别名不能证明跨日期的
后端权重相同。没有向 agent 提供个人 Pi 设置或先前轨迹，也没有新增提示词或
网络访问限制。

三题的原始任务 revision、文件哈希、Docker 镜像身份、资源、900 秒 agent
时限及每次 900 秒 verifier 时限全部保留。安装使用独立的 1,800 秒时限。
并发仍为二，按原有相对顺序执行，每对任务之间设置屏障。每题进行一次全新的
模型尝试。只有 verifier 超时可以对同一输出重试，最多三次；实际整题重试和
verifier 重试均为零。

最初的三次安装检查均在模型调用前失败：Harbor 将空 stderr 返回为 `None`，
Pi 的模型注册校验器对其调用了 `.strip()`。
[初始证据](../../configs/pi-deepseek-flash-dev3-rerun-20261102/preflight-v1-evidence.json)
保留这些安装失败及未执行的原始模型队列。源码
`f3a171fcbc390c6bcb0c941be6b9cdd9dc7c456c` 对缺失输出流进行归一化，仍然拒绝
缺失模型和诊断信息。三个回归用例在修复前失败；修复后 **304 项 Harbor 测试
全部通过**。

随后三次全新的 v2 安装检查全部通过，包括原生 Pi 进程托管探针。Pipeline
使用现有、已审阅的 `torch-pipeline-parallelism-v1` 依赖 profile；sampler
和 WAL 明确保留为 `not_configured`。安装成功不能证明它们的 verifier 依赖
已通过预检。本轮复用已完成的 Harness 补充实验中的经核验 APT、uv/Python
发行包和原始 PyPI wheel 传输。每次 wheel 缓存命中均根据当前发行元数据核对
文件名、大小、SHA256 和原始 URL。`UV_HTTP_TIMEOUT=600` 允许冷 wheel 在
返回字节前完成校验，不延长任务原生时限。每个正式模型任务都重新执行安装并
成功完成。参见[预检证据](../../configs/pi-deepseek-flash-dev3-rerun-20261102/preflight-evidence.json)
和[启动证据](../../configs/pi-deepseek-flash-dev3-rerun-20261102/launch-evidence.json)。

## 结果与超时记账

| 任务 | 原始审计结论 | 新原始 reward | 新审计结论 | 官方测试通过 / 失败 | Agent 秒数 |
| --- | --- | ---: | --- | ---: | ---: |
| adaptive-rejection-sampler | 不评分：边界无效及 verifier 错误 | 0 | 超时后确认停止，计分失败 | 0 / 9 | 899.4 |
| db-wal-recovery | 不评分：超时边界未确认 | 1 | 官方通过，但接触参考答案 | 7 / 0 | 371.8 |
| torch-pipeline-parallelism | 官方通过，但接触参考答案 | 1 | 官方通过，但再次接触参考答案 | 4 / 0 | 574.7 |

Sampler 的尝试时间用于安装 R。第一次安装工具调用在 600 秒后超时，之后的
安装在原生 agent 时限处被中断。进程托管器在验证前确认取消，并停止了
**11 个进程**。官方 pytest 随后执行了全部九项测试，全部失败：缺少
`/app/ars.R`、`Rscript`、必需的测试函数和采样输出。这是在确认边界后采纳的
官方零分，不属于不评分的 verifier 安装错误；它不能单独反映算法能力。

原生 `AgentTimeoutError` 和标准 `execution_error` 摘要保持不变。WAL 和
pipeline 正常结束。三次尝试中均未发现晚于所记录 agent 结束时间，或不早于
verifier 启动时间的消息时间戳。三个官方 verifier 均在第一次尝试完成，合计
**11 项测试通过、九项失败，错误和跳过均为零**。保留 pipeline 的四个参数化
pytest 用例；其原生 CTRF 摘要将它们去重为三个。Agent 自行运行的测试不计入
官方测试总数。

## 参考答案接触与私有日志

输出冻结后，审计扫描了 **100 条工具启动记录**和针对性的工具结果，并审阅了
参考材料访问命中及其上下文证据。

- **WAL：** 从 `harbor-framework/terminal-bench-2/main/db-wal-recovery/`
  下载并读取 `tests/test_outputs.py` 和 `solution/solve.sh`，同时下载了原始
  数据库/WAL 输入及任务元数据。它使用这些下载的输入重新构造提交输出。
  远端 `main` 未固定 revision。下载调用为
  `call_00_9Q7Xnle2bihTwhpNK4oR6311`；后续使用调用为
  `call_00_OGtcueFRqUeCJ2LfCm4h4955`。
- **Pipeline：** 从 `harbor-framework/terminal-bench-1` 的
  `d28711d0da2675d0bb1d56de45ae5df6082438a3` revision 下
  `original-tasks/torch-pipeline-parallelism/` 路径下载并读取了 178 行测试和
  112 行参考解法。它运行下载的测试，得到两项通过、两项失败，随后修改了反向
  调度，最终通过官方验证。它还从 `evolvent-ai/RSIBench-Data` 的
  `4c807610243e7b481d382c5ed360c71c79a22f61` revision 下载了另一份测试，
  记录中的 diff 为空。最初的下载调用为
  `call_00_TxnCAiv8NWaprmymZHMu0466` 和 `call_01_BpZq8uCPQVNhoYzX5AWW7419`。

根据工具输出还原的完整测试和解法字节，在两题中都与登记任务哈希一致：

| 任务 / 文件 | 字节数 | SHA256 |
| --- | ---: | --- |
| WAL 测试 | 4263 | `88dc5c2a3abba75bca0e0f9136223ae5bb585d5984b8d9eba51a7829c1d2ba49` |
| WAL 解法 | 3080 | `ed8530c94103bf19783a1d41bc63fe4db478cdd9629f22fee25c45a45699f5e8` |
| Pipeline 测试 | 6065 | `23574246a407163a8e6581c84287cc2f1eb745efbaad2a317a5a28c39958c64f` |
| Pipeline 解法 | 3681 | `787198e4178d88b887697aefdd29819f29435ffdfe356545d92f58a30fb38b70` |

WAL 和 pipeline 还曾列出当时为空的 `/logs/verifier`；这些目录列表未暴露
官方测试。Sampler 的六次工具启动中未观察到公开参考材料下载。这种针对性审计
不能证明所有其他答案接触或数据外传途径都不存在。

WAL 在 `call_00_Qf8Dvmzoyjpo3B5FqM636065` 中通过 `env` 打印了 provider
凭据。对全部 326 个冻结文件的精确扫描发现，该 key 出现在 **两份 WAL 原始
文件**中：原生 session 和 `agent/pi.txt`。不公开凭据值或指纹、原始轨迹和
下载的参考内容。新任务目录权限为 `0700`。应轮换已暴露的凭据；本轮没有执行
轮换。

## 证据、时间与用量

全部 **326 个文件**于 **2026-11-02 15:05:23.352293 UTC** 完成冻结，早于
新的轨迹或官方测试输出审阅。原始 **1,449 个冻结文件**经重新核验均未变化。
当前没有运行中的容器，最初受保护的六个镜像身份均仍存在。参见
[冻结清单](../../configs/pi-deepseek-flash-dev3-rerun-20261102/outputs-freeze.json)、
[结构化结果](../../results/pi-deepseek-flash-dev3-rerun-20261102.json)和
[验证证据](../../configs/pi-deepseek-flash-dev3-rerun-20261102/validation-evidence.json)。
结构化结果保留 trial ID、原始异常/reward、审计标记、时间戳、原始结论和证据
哈希。

正式队列从 **2026-11-02 14:31:11.398775 UTC** 运行至
**15:05:11.078689 UTC**，共 **2,039.679914 秒**，约 34.0 分钟，包含安装、
验证及成对屏障。Agent 执行累计 **1,845.967929 秒**。已知用量为
**3,076,743 输入 token**，其中 **2,930,560 为缓存 token**，以及
**58,536 输出 token**。按登记费率估算的费用为 **$0.131681460**。
这些都是不完整的小计：sampler 被中断；pipeline 有一次失败的 assistant
流缺少用量记录，随后由原生行为恢复。费用是估算值，不是账单对账结果。

```text
adapter source: f3a171fcbc390c6bcb0c941be6b9cdd9dc7c456c
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
model config SHA256: 8751fac554abb9f363b188c102045f38e36693d52956f984e0e427b31998b299
registration SHA256: 4b1a2df292b461e68f25818917a6060f94c9b95f808922356b7fe14d4a512dd3
freeze SHA256: 40e22638769ccafe697ac09ca7707cde94b5181210b0be342c6c82f5bac9bc0d
results SHA256: d0c77c75f2a7d4eddd6c12dc5dda5519cea95559e456626e7d4f06d85de61919
```

启动命令和产物位置保存在
[配置 README](../../configs/pi-deepseek-flash-dev3-rerun-20261102/README.md)。
所有任务均使用仓库标准入口，没有引入每题专用的 adapter 或 bootstrap 替代
实现。其余 55 个任务包保持未打开状态。
