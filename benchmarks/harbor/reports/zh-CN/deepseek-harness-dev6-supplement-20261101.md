# DeepSeek 官方 Harness 的六题补测

维护者要求重新尝试后，之前未计分的六道题于 **2026 年 11 月 1 日**补跑。
本次补测得到 **4 题通过、2 题计分失败、0 题未计分错误**。六次模型执行均正常完成，每个官方验证器均在第一次尝试内完成。

原始 [34 题实验](deepseek-harness-dev34-20261030.md)仍为
**22 题通过、6 题失败、6 题未计分错误**。这六次尝试是独立记录、根据原始结果
选取的开发补测。将原始 28 次有效尝试与这六次新尝试结合，得到描述性的混合覆盖结果：**34 题中 26 题通过、8 题失败，无剩余未计分题目**。 它们不构成独立基准或两次取优的成绩，也不能证明
harness 的因果改进。原始已计分的六道失败题没有重跑。

[审计结果](../../results/deepseek-harness-dev6-supplement-20261101.json)保留每个
新试次、原始奖励/异常、分析结果、官方测试数量、时间、用量及证据哈希。
[v2 登记](../../configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json)
和[配置历史](../../configs/deepseek-harness-dev6-supplement-20261101/README.md)
记录模型运行前的调整。全部六道新输出于 **2026-11-01 16:56:07.773103 UTC**
[冻结](../../configs/deepseek-harness-dev6-supplement-20261101/outputs-freeze.json)，
之后才查看新轨迹或隐藏断言；重新校验了 **590 个文件**。
原始日志保留在本地。

## 逐题结果

六道题在原始实验中的分析分数均为 `null`。`—` 表示未计分或没有模型执行。
Pi 数值保留历史审计口径；`‡` 标记其接触了公开参考测试/解答的流水线并行通过结果。

| 任务 | 原始未计分原因 | Pi 审计分数 | 新原始奖励 | 新审计结果 | 官方通过 / 失败 | Agent 秒数 |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| multi-source-data-merger | 验证：pyarrow 下载失败 | 1 | 1 | 通过 | 3 / 0 | 29.6 |
| pytorch-model-cli | 安装：uv 安装器 TLS 错误 | 0 | 0 | 失败 | 5 / 1 | 628.4 |
| pytorch-model-recovery | 安装：1,800 秒超时 | 1 | 1 | 通过 | 5 / 0 | 110.1 |
| query-optimize | 执行：终止运行的 API 传输错误 | 0 | 1 | 通过 | 6 / 0 | 270.5 |
| torch-pipeline-parallelism ‡ | 验证：CUDA 依赖下载失败 | 1 | 0 | 失败 | 2 / 2 | 632.4 |
| torch-tensor-parallelism | 验证：超时后 torch 下载失败 | 1 | 1 | 通过 | 13 / 0 | 73.4 |

- **pytorch-model-cli**: 正常完成。五项官方检查通过；test_cli_tool_output 失败，50 个测试 MNIST 预测中有 14 个与固定期望值不符（图像 0：预测 7，期望 2）。产物和可执行性检查通过。这是可计分的断言失败，不是依赖或验证器错误。
- **torch-pipeline-parallelism**: 正常完成。存在性和无 hook 检查通过；两个 world size 用例均在 microbatch 0 的反向值比较中失败。world size 1：rank 0 的 lm_head.bwd 最大差异为 0.04166729375720024。world size 2：rank 0 的 model.layers.1.bwd 最大差异为 0.01778167486190796。子进程异常来自这些官方断言，不是验证器基础设施错误。

这些是官方测试发现，不是穷尽性的根因证明。

六次有效评测共执行 **37 个官方用例：34 个通过、3 个失败、0 个错误/跳过**。不计入 agent 自测。 原始奖励和标准汇总保持不变；官方零分不自动等于有效的计分失败。
安装错误、终止运行的 API 错误和验证器依赖/执行错误单独列出。原生 agent 超时
只有在停止边界已确认且官方测试完整执行、形成有效评测时才可计分。本次 **6 个正常结束边界**全部确认；**agent 结束后或验证开始时及之后的事件数为 0，agent 超时为 0，额外验证尝试为 0**。

## 准备失败及校验下载

最初直接下载的准备方案设置 `UV_HTTP_TIMEOUT=120`。数据合并、PyTorch CLI 和
查询优化的三次仅安装试次通过。模型恢复题在验证器依赖阶段达到
**1,800 秒安装时限**。控制器在第二组完整结束后停止，最后一组和所有模型任务
均未启动，没有中断任何运行中的试次。
[初始证据](../../configs/deepseek-harness-dev6-supplement-20261101/preflight-v1-evidence.json)
保留全部四次实际试次。六道选中题目的状态为：**3 次通过、1 次安装失败、2 次未启动、0 次模型执行**。
最初的模型队列被后续方案取代，从未运行。

v2 登记前增加了可复用、可选的 PyPI wheel 辅助服务。它转发 PyPI 当前原始索引
元数据，保留版本、依赖要求、撤回标记、哈希及额外索引设置。wheel 只有在匹配
当前原始发布元数据的文件名、大小、SHA256 和 HTTPS 来源，并校验完整下载字节后
才会提供。跨进程锁保护共享下载；元数据不可用或缓存损坏时拒绝使用。
源码分发包和原始额外索引不经过此 wheel 缓存。

v2 设置 `UV_DEFAULT_INDEX=http://127.0.0.1:18744/simple` 和
`UV_HTTP_TIMEOUT=600`，允许未缓存的 wheel 在发送任何响应正文前完成完整校验。
安装时限仍为 **1,800 秒**。原始 APT 源和已校验的 APT 索引、uv/Python 发布包
下载通道保持不变。没有修改任务镜像、包版本要求、官方测试或原生 agent/验证器
时限。包缓存和新增依赖准备会影响运行时间，因此这不是对模型行为或下载通道
进行隔离控制的实验。

**六道全新 v2 仅安装检查均在任何模型任务前通过**，包括 SDK 初始化、Linux
进程监管和精确任务修订对应的依赖配置。新增五项配置，模型恢复沿用已有配置。
它们保留原始 Python、包和索引要求，只在 `/tmp` 执行 `pytest --version`，
不执行任务代码或断言。
[预检证据](../../configs/deepseek-harness-dev6-supplement-20261101/preflight-evidence.json)
和[启动登记](../../configs/deepseek-harness-dev6-supplement-20261101/launch-evidence.json)
均先于模型运行。六道正式任务均重复执行并通过相同的依赖配置。CLI 安装耗时 **1,690.4 秒**，仍在未变的 1,800 秒时限内；先前预检通过并不意味着后续下载没有延迟。

完整 Harbor 测试套件 **301 项通过**，包括 **16 项 wheel 缓存契约测试**。
使用全新临时 uv 缓存、真实原版 **uv 0.9.5** 的下载冒烟检查也通过，
**模型调用为零**；[探测记录](../../configs/deepseek-harness-dev6-supplement-20261101/transport-v2/transport-probes.json)
保留两个版本的冒烟检查和一次完成校验的分段下载实验。冻结的下载日志包含 **675 条原始发布元数据事件、270 次已校验 wheel 响应：224 次缓存命中、46 次非缓存响应、53 个不同产物**，来自 **12 个辅助服务**，**记录的下载错误为 0**。每次 wheel 响应均有同一辅助服务此前对应的原始发布元数据。

## 保留的模型配置及审计

| 属性 | 值 |
| --- | --- |
| 上游 | `deepseek-ai/deepseek-harness` `0.2.2-alpha.2`，源码 `f3803c96974ad4a94195fb97e5c637e9c2a3afe3` |
| 配置 | `sdk-minimal`；与原始运行相同的离线 SDK/runtime 分发包 |
| 模型/API | `deepseek/deepseek-flash`，high 推理，`https://api.deepseek.com/anthropic` |
| 生成设置 | 原生提示词/工具/压缩/请求重试；temperature 和 SDK max_tokens 未设置；原生上限 256,000 |
| 适配器 | 共享冻结源码 `eff073b1601435305155cad92b6ee9e2250fbbdc` |
| 下载通道源码 | `dc32b26194a06e7b070c5e8876d26ea0fcf3a7d3`；已检查登记的文件哈希 |
| 时限 | 每题 agent 900 秒；验证器 900 秒，查询题为 1,800 秒；安装 1,800 秒 |
| 调度 | 原始相对顺序；并发二，每组完成后再推进；每题一个新的正式尝试，无自动整题重试 |
| 验证器重试 | 仅超时重试，最多三次总尝试，输出及原始单次时限不变 |

冻结的适配器相对原始源码仅修改了 `bootstrap.py` 中经过审核的依赖预检；模型
驱动、提示词集成、监管器和验证器的字节完全一致。用户的上游检出目录保持不动。
全新隔离会话不接收之前的输出、诊断、解答或个人配置。其余 **55 道题保持未打开**。
没有加入 SDK 服务生命周期修复；原始 KV/PyPI 失败保持不变。

11 月 1 日检查的官方[agent 集成指南](https://api-docs.deepseek.com/quick_start/agent_integrations/)
仍将该别名映射到 DeepSeek-V4.1-Flash-1017，见
[别名证据](../../configs/deepseek-harness-dev6-supplement-20261101/model-alias-check.json)。
它是可变别名，不能证明跨日期使用相同后端检查点。Pi 使用 OpenAI 兼容接口，
输出上限为 384,000 token。其采样器/WAL 成绩存在无效/未确认的历史边界，流水线
并行通过结果带有参考资料接触限制。在这组选出的六道题上，Harness 和 Pi 各通过 **4 题**；Harness 新通过查询优化、失去流水线并行通过，仍保留 Pi 的参考资料接触限制。混合覆盖中 **32 道共同有效计分题**上，Harness 通过 **25 题**，Pi 通过 **26 题**。新增通过为 DNA 组装和查询优化；失去通过为 KV、PyPI 和流水线并行。这些失去通过的题分别带有 KV/PyPI 生命周期及 Pi 流水线参考资料接触限制。

冻结后扫描了 **98 次工具调用**，并查看 **3 个候选及对应输出**：CLI 的两次调用访问公开 MNIST 数据，流水线的一次调用检查根目录、Python 路径及环境。未在这些记录中观察到基准参考测试/解答。所查看的环境没有以敏感凭证名称命名的条目；精确匹配在 **590 个冻结文件中发现该已授权服务商密钥的文件数为 0**。 这种定向审计不能穷尽证明不存在资料接触或数据外传。
SDK 已知用量为 **1,298,682 个输入 token**，其中 **1,242,112 个缓存 token**，以及 **79,429 个输出 token**。六道试次均报告 `usage_is_partial=false`；费用仍未知。 缓存 token 已包含在输入中，不再重复相加；这些数据是 SDK 已知用量小计，未查询服务商账单。正式队列从 **2026-11-01 15:50:21.232772 UTC** 运行至 **16:55:21.072680 UTC**：墙钟耗时 **3,899.8 秒**，agent 累计耗时 **1,744.3 秒**。队列时间包含安装、验证及组间等待，不包含之前的预检和下载探测。

```text
v2 plan SHA256: 69eb8272f3fcd125e062387f7f725c80f12b56b8a622d6a616d23f8e0e174a93
freeze SHA256: ee6a3c6a4f57b6da2ffcc04e81e54e888949285054aff8e7a218ce0f330671f3
results SHA256: 412a0d0acd266d5573ff722a2e5376ab0264b457821d0d603cf8b3f0e663d067
preflight evidence SHA256: e973e6d280171287c8c60b7888834b56259f897aac67e8ffa6c23daad39e3e06
original results SHA256: e94ca1e201d032617e9d4649f2cbfbb60127c1257e7a0f3b2696fea808288396
source archive SHA256: 0a851c705c243519cc573d077d8cf23295591498825d82b795b43b37255d43e4
distribution SHA256: d8f6157c880dfa5ae65b6c176dd86b1e32f5f31709f8f29fa7170db45d2fb9d6
runtime SHA256: 28e1eaeac3c594d2ce74c67c4f1e179c58ccf3d4dbb8c0faa719bec5745805f2
wheel-cache source SHA256: ced6bd7c1bf2b6ac1964c39d057708ba0e52c37c61a609651c49105ea145ea74
wheel audit SHA256: ef8385be4d1387b72014dca1e89b1281fed347714f9bd3e5f9e050b501e7366a
```

## 复现

使用共享冻结的适配器检出目录和登记的本地产物。编排器调用标准
`python -m harbor_adapter run --config ...` 入口，不创建每个任务独立的适配器副本。
发布的配置保留本地绝对路径，复现时应使用等价的固定产物及新任务名。
不要覆盖或重放已登记的任务。

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/dsh-harbor-venv"
export UV_CACHE_DIR="$PWD/.cache/uv"
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json \
  --phase preflight
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json \
  --phase model
```

已授权的服务商密钥仅通过进程环境提供。英文和简体中文报告包含相同的结果、
限制、表格、标识符、命令和哈希。
