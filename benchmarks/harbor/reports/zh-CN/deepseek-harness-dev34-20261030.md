# DeepSeek 官方 Harness 在 Pi 的 34 道开发题上的结果

后续：另行授权的 [11 月 1 日六题补测](deepseek-harness-dev6-supplement-20261101.md)
在这六道未计分题上获得四题通过、两题计分失败。以下原始结果和审计保持不变。

**34 个注册作业已于 2026 年 10 月 31 日全部结束**：**22 道官方验证通过、
6 道计分失败、6 道因错误不计分**。其中实际执行模型的有 32 道，另两道在安装
阶段失败。两道计分失败存在已确认的 SDK 服务生命周期限制。本报告描述通过
官方 Python SDK 运行的 Harness `sdk-minimal` 配置，不能代表 Harness 的所有
接口，也不构成完整的 34 道题通过率。

在**双方都有有效评分的 26 道题**上，本配置通过 **21 道**，
[Pi](pi-deepseek-flash-dev34-20261024.md) 通过 **22 道**。
`dna-assembly` 从失败变为通过；`kv-store-grpc` 和 `pypi-server` 从通过变为
失败。后两题的服务在 agent 自测时可用，在正式验证时已不可用。独立的无密钥
探针确认，正常关闭 SDK 会停止后台服务。因此，这一对照不能证明模型或
harness 能力存在因果差异。

[审计结果](../../results/deepseek-harness-dev34-20261030.json) 保留全部 34 个
trial ID、原始与分析结果、官方测试数量、耗时、用量、诊断及证据哈希。
[实验注册](../../configs/deepseek-harness-dev34-20261030/experiment.json) 和
[配置历史](../../configs/deepseek-harness-dev34-20261030/README.md) 保留准备与
执行决策。全部输出于 **2026-10-31 15:47:11.582274 UTC** 冻结，之后才查看
本次解题轨迹和隐藏测试内容。
[冻结清单](../../configs/deepseek-harness-dev34-20261030/outputs-freeze.json)
覆盖 **2,506 个文件**，审计时已逐一重新计算哈希。原始轨迹仅保存在本地。

## 配置与保留的实验协议

| 属性 | 值 |
| --- | --- |
| 题池 | Pi 已使用的同一组 34 道开发题，题目版本、文件、镜像、资源和官方测试均不变；其余 55 道题保持未打开 |
| Agent | 官方 `deepseek-ai/deepseek-harness`，版本 `0.2.2-alpha.2`，源码 `f3803c96974ad4a94195fb97e5c637e9c2a3afe3` |
| 配置 | 上游推荐用于基准测试的 `sdk-minimal`，通过公开 Python SDK 驱动 |
| 行为 | 原生系统提示词、持久 bash、图片读取、工作目录工具、上下文压缩、请求重试及生成默认值；每题使用全新目录和会话 |
| 隔离 | 不载入个人指令、技能、扩展、设置或历史会话；任务工具在题目容器内执行 |
| 模型 | `deepseek/deepseek-flash`，`high` 推理，官方 Messages 端点 `https://api.deepseek.com/anthropic` |
| 生成设置 | 不设置 temperature 和 SDK `max_tokens`；上游输出上限为 256,000 |
| Adapter | 冻结源码 `5b503ab6d04af2f6a719ec0dbe5418bfad4bf128`，位于 `jobs/deepseek-harness-runtime-source` |
| 限制 | 保留题目原生 agent / 验证器时限和资源；安装时限为 1,800 秒 |
| 队列 | 与 Pi 顺序一致；并发为二，每对题结束后才进入下一对；不重试整题 |
| 验证 | 保留原始脚本与每次验证时限；仅验证器超时可在同一 agent 输出上重试，总共最多三次 |

10 月 30 日和 31 日检查的官方
[agent 接入指南](https://api-docs.deepseek.com/quick_start/agent_integrations/)
将 `deepseek-flash` 映射到 DeepSeek-V4.1-Flash-1017；
[别名记录](../../configs/deepseek-harness-dev34-20261030/model-alias-check.json)
保存了后一次检查。它仍是可变别名，不能证明不同日期使用完全相同的后端
检查点。Pi 使用其原生 OpenAI 兼容端点和 384,000 token 输出上限。两次实验
均未施加 Nano 的 100 次回复限制或收尾提醒。端点、预算、日期和生命周期
差异意味着本实验比较的是完整配置。

用户原始的上游检出保持干净且未修改。构建在隔离副本中进行，使用上游冻结
的 pnpm 锁文件（Node 26.7.0、pnpm 11.28.5）。八项构建关卡和官方无密钥
SDK 冒烟测试全部通过。离线分发包含 SDK、原生运行时和五个依赖 wheel。
源码内容、分发内容及文件权限均已固定。

```text
plan SHA256: fb59d5618c44e691babb80b2ea8323eb45edf9f45383e61344d747b870bc6d6e
freeze SHA256: cc421c1429450ac41d355d0df8333f4ab10ca4da0bf47f24bc3892d0724d9c24
results SHA256: e94ca1e201d032617e9d4649f2cbfbb60127c1257e7a0f3b2696fea808288396
selection SHA256: 4572b1cc432a16b9c5d1dd554c8d2189ae80414f386a90bf03829bc4d0c3da85
source archive SHA256: 0a851c705c243519cc573d077d8cf23295591498825d82b795b43b37255d43e4
distribution SHA256: d8f6157c880dfa5ae65b6c176dd86b1e32f5f31709f8f29fa7170db45d2fb9d6
runtime SHA256: 28e1eaeac3c594d2ce74c67c4f1e179c58ccf3d4dbb8c0faa719bec5745805f2
lifecycle diagnostic SHA256: 4257a96a3415a7d389fb7b3fb10f819341714ba833b0911eb2a6468171e70c47
```

## 安装、执行边界与错误记账

**全部 34 道仅安装预检均在首个模型作业开始前通过**，包括 SDK 初始化和
Linux 进程监督探针。QEMU 的 `qemu-alpine-ssh-v1` 与模型恢复题的
`pytorch-model-recovery-v1` 依赖配置通过；其余 **32 道明确标记为
`not_configured`**。
[模型执行前的元数据修正](../../configs/deepseek-harness-dev34-20261030/profile-metadata-amendment.json)
更正了沿用的历史配置数量描述，没有改变任何执行设置。
[预检证据](../../configs/deepseek-harness-dev34-20261030/preflight-evidence.json)
不保证后续依赖网络的安装仍能成功。

首次 WAL 安装冒烟失败，因为 Python `dsh` 启动器即使查询版本也需要显式
`DSH_HOME`。Adapter 在注册前为版本检查提供了隔离目录，修正后的冒烟通过。
两次记录均保存在[安装证据](../../configs/deepseek-harness-dev34-20261030/setup-evidence.json)，
都不属于计分模型尝试。验证包括该集成修正之前的 280 项 Harbor 测试，以及
修正之后的 11 项 DeepSeek 专项测试。最终完整 Harbor 测试再次全部通过，共
280 项。首次调用通过 273 项，另七项本地 HTTP fixture 被沙箱 socket 权限
阻止；允许本地 socket 后完整重跑，在 17.56 秒内全部通过。

**全部 32 次模型执行**都在官方验证前确认了完成或取消边界。没有记录到
agent 结束之后，或验证器开始时及之后的 SDK 事件。三次 agent 超时分别是
采样器、模型提取和流水线并行，均使用原生 900 秒时限；取消过程分别停止了
**10、4、8 个进程**。采样器和模型提取具有有效的官方失败结果；流水线并行
另有验证器依赖错误，因此不计分。

原始奖励保留为 **22 个一、10 个零、两个 null**。未修改的标准汇总包含
**28 个 `scored`、四个 `execution_error`、两个 `setup_failed`**。
分析审计将官方断言失败与安装未完成、终止性的 API 错误及验证器错误分开；
不改写原生异常或奖励。

| 未计分题目 | 类别与证据 |
| --- | --- |
| pytorch-model-cli | 安装：获取原始 uv 0.9.11 安装器时，在 `releases.astral.sh:443` 发生 curl 35 / `SSL_ERROR_SYSCALL`；原生 `NetworkConnectionError`，未执行模型 |
| pytorch-model-recovery | 安装：在 `verifier_dependencies` 阶段达到 1,800 秒，原生 `AgentSetupTimeoutError`；SDK / 监督检查通过，但本次正式依赖检查未完成；未执行模型 |
| multi-source-data-merger | 验证器：下载或解压 `pyarrow==22.0.0` 时发生 `UV_HTTP_TIMEOUT=30` 超时；官方 pytest 未开始 |
| query-optimize | 执行：SDK `finish_reason=error`，同一提供方请求尝试六次（含五次原生请求重试）后因 `TRANSPORT` 错误终止；原生 `NonZeroAgentExitCodeError`；后续官方测试发现 SQL 输出缺失 |
| torch-pipeline-parallelism | 验证器：确认 agent 超时取消后，下载 `torch==2.7.0` 所需的 `nvidia-cusolver-cu12==11.7.1.2` 超时；官方 pytest 未开始 |
| torch-tensor-parallelism | 验证器：首次达到 900 秒；第二次下载 `torch==2.7.0` 时发生 `UV_HTTP_TIMEOUT=30` 超时；官方 pytest 未开始 |

共有**三次额外验证尝试**：采样器两次达到 900 秒超时，第三次在 26.3 秒内
完成；张量并行一次达到 900 秒超时，第二次因依赖错误结束。重试使用同一
输出和原始脚本。依赖失败未触发重试。没有重跑任何完整题目、模型输出或
安装失败。Agent 内的原生请求重试与这些验证器重试、整题重试分别记账。

## 逐题结果

`—` 表示无分析评分或未执行，依列含义区分。Pi 列采用审计后评分，而非原始
奖励。`†` 表示服务生命周期限制；`‡` 表示 Pi 曾访问参考材料的流水线通过结果。

| 题目 | Pi 审计评分 | Harness 原始奖励 | Harness 审计结果 | 官方测试通过 / 失败 | Agent 秒数 |
| --- | ---: | ---: | --- | ---: | ---: |
| adaptive-rejection-sampler | — | 0 | 超时；确认停止，失败 | 4 / 5 | 899.4 |
| build-cython-ext | 1 | 1 | 通过 | 11 / 0 | 593.1 |
| cancel-async-tasks | 0 | 0 | 失败 | 5 / 1 | 26.3 |
| cobol-modernization | 1 | 1 | 通过 | 3 / 0 | 172.4 |
| db-wal-recovery | — | 1 | 通过 | 7 / 0 | 34.1 |
| fix-code-vulnerability | 1 | 1 | 通过 | 6 / 0 | 42.1 |
| git-multibranch | 1 | 1 | 通过 | 1 / 0 | 83.5 |
| kv-store-grpc † | 1 | 0 | 失败 | 5 / 2 | 45.8 |
| log-summary-date-ranges | 0 | 0 | 失败 | 1 / 1 | 21.0 |
| merge-diff-arc-agi-task | 1 | 1 | 通过 | 5 / 0 | 110.5 |
| model-extraction-relu-logits | 0 | 0 | 超时；确认停止，失败 | 0 / 1 | 899.4 |
| multi-source-data-merger | 1 | 0 | 未计分：验证器错误 | — | 27.8 |
| nginx-request-logging | 1 | 1 | 通过 | 8 / 0 | 138.0 |
| openssl-selfsigned-cert | 1 | 1 | 通过 | 6 / 0 | 36.2 |
| pypi-server † | 1 | 0 | 失败 | 0 / 1 | 40.2 |
| pytorch-model-cli | 0 | — | 未计分：安装错误 | — | — |
| pytorch-model-recovery | 1 | — | 未计分：安装错误 | — | — |
| qemu-alpine-ssh | 1 | 1 | 通过 | 1 / 0 | 270.2 |
| query-optimize | 0 | 0 | 未计分：API 错误 | 2 / 4 | 231.7 |
| regex-log | 1 | 1 | 通过 | 1 / 0 | 90.3 |
| torch-pipeline-parallelism ‡ | 1 | 0 | 未计分：验证器错误 | — | 899.3 |
| torch-tensor-parallelism | 1 | 0 | 未计分：验证器错误 | — | 131.3 |
| write-compressor | 1 | 1 | 通过 | 3 / 0 | 143.6 |
| constraints-scheduling | 1 | 1 | 通过 | 3 / 0 | 24.3 |
| custom-memory-heap-crash | 1 | 1 | 通过 | 6 / 0 | 131.7 |
| dna-assembly | 0 | 1 | 通过 | 1 / 0 | 944.5 |
| llm-inference-batching-scheduler | 1 | 1 | 通过 | 6 / 0 | 503.8 |
| path-tracing | 1 | 1 | 通过 | 5 / 0 | 229.8 |
| schemelike-metacircular-eval | 1 | 1 | 通过 | 1 / 0 | 902.8 |
| caffe-cifar-10 | 1 | 1 | 通过 | 6 / 0 | 2200.5 |
| circuit-fibsqrt | 1 | 1 | 通过 | 3 / 0 | 461.1 |
| mteb-leaderboard | 1 | 1 | 通过 | 2 / 0 | 1172.2 |
| regex-chess | 1 | 1 | 通过 | 4 / 0 | 1907.7 |
| build-pov-ray | 1 | 1 | 通过 | 3 / 0 | 891.9 |

测试数量来自最终官方 pytest 汇总，保留参数化用例；不累加 agent 自测或
嵌套的上游测试。**28 次有效评估**共执行 **118 个用例：107 通过、11 失败、
零错误或跳过**。因 API 中断而未计分的查询优化题另有**两个通过、四个失败**
用例，其余五道未计分题未进入官方 pytest。

| 计分失败题目 | 官方断言或缺失产物 |
| --- | --- |
| adaptive-rejection-sampler | 确认超时取消后，缺少 `Rscript` 和生成的采样文件；缺少 R 时安装 R 是题目明确要求，因此属于任务失败，而不是验证器依赖排除项 |
| cancel-async-tasks | 多余任务的清理消息为零，预期为二 |
| kv-store-grpc † | 5328 端口未监听；连接被拒绝 |
| log-summary-date-ranges | 当天 ERROR 数为 74，预期 370 |
| model-extraction-relu-logits | 确认超时取消后缺少 `/app/stolen_A1.npy` |
| pypi-server † | 从 `localhost:8080` 安装 `vectorops==0.1.0` 失败，本地索引不可达 |

这些是官方验证发现，并非穷尽根因的证明。

## SDK 服务生命周期诊断

KV 的 agent 曾成功调用 `SetVal` / `GetVal` 并读取值 123。PyPI 的 agent
启动了 `nohup` 服务、获取了索引，并在独立虚拟环境中安装和执行了该包。
SDK 上下文关闭后，两个服务均无法被官方验证器访问。

固定版本的上游 SDK 在正常关闭时会释放托管终端及其后代进程。共享的 Linux
监督器允许正常完成后保留解题服务，但无法保留已被 SDK 停止的服务。
冻结后的[诊断](../../configs/deepseek-harness-dev34-20261030/sdk-lifecycle-probe.json)
使用上游无密钥 mock fixture 和同一固定运行时，只有**两个本地 mock 请求，
零次真实模型调用**。通过 `nohup` 启动的 Python HTTP 服务在 **SDK 关闭前
可达，关闭后不可达**。
[可复用探针](../../scripts/probe_deepseek_lifecycle.py) 记录了自身、fixture 和
运行时的哈希：

```bash
jobs/dsh-harbor-venv/bin/python benchmarks/harbor/scripts/probe_deepseek_lifecycle.py \
  --upstream-source jobs/deepseek-harness-build-f3803c9/source \
  --runtime jobs/deepseek-harness-build-f3803c9/source/dist-exe/deepseek-harness-sdk-runtime-linux-x64
```

该诊断发生在全部基准输出冻结之后。它确认了本次 SDK 集成的生命周期限制，
不能证明换一种生命周期后两道题会通过所有官方断言。两个零仍作为本配置的
计分失败保留。没有在注册运行中修复生命周期、重启服务或重新评分。

## 与 Pi 的对照解释

Pi 审计记录为 **26 通过、六失败、两个历史超时不计分**。其采样器边界无效，
WAL 边界未经确认；流水线并行通过结果曾访问公开参考测试和解答。这些限制
继续保留在 [Pi 报告](pi-deepseek-flash-dev34-20261024.md) 中。

共同有效的 26 道题中，**Harness 通过 21 道 / Pi 通过 22 道**。唯一新增
通过是 `dna-assembly`；两道退步是 `kv-store-grpc` 和 `pypi-server`，均有
生命周期限制。`db-wal-recovery` 本次通过，但 Pi 未计分，因此不算成对提升。
采样器本次有有效官方失败，但同样没有有效 Pi 对照。六道本次未计分题也
不能用于推断提升或退步。共同子集由能否有效评估决定，不是注册 34 道题池的
无偏替代。这里不提供统计控制下的排名、完整成对通过率，也不声称观察到的
变化只由 harness 导致。

## 材料访问、用量、耗时与复现

冻结输出后，针对基准仓库、隐藏路径和环境访问的定向扫描覆盖了 **675 次
记录的工具调用**及匹配候选的输出。该扫描未观察到从外部获取 Terminal-Bench
参考材料或访问官方隐藏测试。日历 `PRODID` 和题目自带 C++ canary 中的
Terminal-Bench 字符串属于正常匹配。MTEB 下载了公开的
`embeddings-benchmark/results` 应用数据，版本为
`3125e8302256ac01d4dd68b6f92902b3e6a78987`，与 Terminal-Bench 测试或解答
不同。该开发题池历史上已被接触；定向扫描不能证明完全不存在材料暴露或
数据外传。

对全部 **2,506 个冻结文件**按字节精确扫描已授权的提供方凭据，发现
**零个文件**包含该值。结论仅限于该密钥及这些文件，不改变历史 Pi 的凭据
发现。原始轨迹和凭据值不发布。维护者 10 月 31 日的授权和模型启动情况
记录在[启动证据](../../configs/deepseek-harness-dev34-20261030/launch-evidence.json)。

| 已知用量或耗时 | 值 |
| --- | ---: |
| 输入 token，含缓存输入 | 25,052,194 |
| 缓存输入 token，已包含在上一项 | 24,346,112 |
| 输出 token | 634,263 |
| 费用 | 未知 |
| Agent 执行秒数之和 | 14,306.464573 |
| 队列墙钟秒数，含安装和验证 | 16,984.894313 |
| 首个作业开始（UTC） | 2026-10-31 11:03:13.156046 |
| 最后作业结束（UTC） | 2026-10-31 15:46:18.050359 |

用量为**已知部分合计**。采样器、模型提取、查询优化、流水线并行、DNA
组装和 LLM 批处理均存在部分用量统计。失败的原生重试与被中断请求可能
缺失用量，即使之后成功完成也一样。不要再次把缓存 token 加到输入中，也
不能据此推断账单。网络状况、安装失败、验证器重试及有效题目集合不同，
无法进行受控的速度或费用对比。

最终验证重新检查了源码、题目和配置哈希、全部预检先于模型的边界、每个
双题屏障，以及预检和正式作业中的 **68 次原始镜像检查**。原始软件包来源
和题目镜像均保留；缓存命中必须匹配文件名、大小和 SHA256。仅对本次新增
镜像引用进行非强制清理，保留受保护镜像。34 个作业均已结束，**零个题目
容器仍在运行**。

[配置 README](../../configs/deepseek-harness-dev34-20261030/README.md) 包含
构建和执行命令。每个作业均从冻结源码使用标准
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`
入口。原生证据保留在 `jobs/deepseek-harness-runtime-source/jobs/`，编排和
镜像事件保留在 `jobs/deepseek-harness-dev34-20261030-orchestration/`。
发布的 JSON 和哈希清单支持检查来源；从源码复现还需要注册的题目包、镜像、
已构建分发及提供方访问权限。已注册的现有作业拒绝覆盖或重放。
