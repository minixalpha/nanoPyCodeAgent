# 中断响应恢复：实现与定向验证

## 状态

传输兼容性修复、有界流式响应恢复、离线测试和独立审查均已完成。线上定向试验
已准备就绪，等待对 OpenRouter 数据传输及 API 费用的明确批准。本实验尚未发出
任何线上模型请求。

## 问题与实现

9 月 12 日和 9 月 14 日的实验在三项不同任务中记录了四次模型响应中断。遍历响应
时发生的 `RemoteProtocolError` 导致整个 agent 运行结束。SDK 1.5.0 使用 `httpx2`，
而 CLI 捕获的是 `httpx.HTTPError`；这两组异常不共享该基类。

修改后同时处理两组 HTTP 异常，并针对响应体读取中的 `ReadError`、`ReadTimeout`
和 `RemoteProtocolError` 最多重试两次，分别延迟 1 秒和 2 秒。保留最后一份完整
对话，只有收到完整回复后才执行工具。中断的回复不消耗已完成回复的轮次预算。
认证失败、无效请求、编程错误和用户取消不由此循环重试。流开始前的错误沿用
SDK 重试策略，不再叠加第二层外部重试。

某次回复首次中断 300 秒后不再调度新的重试。该调度窗口不会取消正在进行的
请求；SDK 超时和外部监督进程的期限仍是独立限制。

Journal v3 新增 `model.failed`，为每次尝试分配独立 ID，记录原始错误、重试意图、
耗时，以及读取响应体前捕获的 generation ID。ATIF 按时间顺序保留失败尝试。
可以对中断生成的费用进行对账，而不会将缺失 token 用量视为完整记账。读取器
继续支持 v1/v2 journal。

## 自动化与离线证据

| 验证 | 结果 |
| --- | --- |
| 完整测试集，锁定 SDK 0.112.0 / httpx | 292 项通过，4 项跳过 |
| 完整测试集，SDK 1.5.0 / httpx2 2.12.0 | 296 项通过 |
| Harbor adapter 与官方 ATIF 兼容性测试 | 24 项通过 |
| 历史中断响应回放，SDK 1.5.0 | 4/4 恢复 |

锁定环境跳过四项明确依赖未安装的 `httpx2` 包的测试。SDK 1.5.0 运行覆盖两组
异常。两次完整测试均仍有畸形工具输入测试中既有的 Pydantic 警告。CI 现在同时
运行锁定依赖环境和 SDK 1.5.0 环境。

真实 SDK 传输测试在看似完整的工具 JSON 到达后中断响应，验证被丢弃的工具始终
不会执行，并检查先前的追加操作仅发生一次。其他测试覆盖重试耗尽、调度窗口、
对话历史保留、中断、永久性错误、费用对账和 journal 版本拒绝。

离线回放通过 SDK 1.5.0 读取原始捕获的响应字节，在 EOF 处抛出记录的传输错误，
并为重试提供合成的成功回复。四个案例均关闭中断响应、重试相同请求、保留失败
尝试，且不执行任何工具：

| 历史试验 | 捕获字节数 | 结果 |
| --- | ---: | --- |
| `torch-tensor-parallelism__EEWJenL` | 280,943 | 恢复 |
| `schemelike-metacircular-eval__Xuw2yU4` | 33,440 | 恢复 |
| `schemelike-metacircular-eval__CJJvMtU` | 1,057,796 | 恢复 |
| `llm-inference-batching-scheduler__S95o8Jv` | 34,318 | 恢复 |

这些回放不发送外部请求，也不提供新的任务分数。它们验证的是响应处理；重试
成功是刻意合成的。

## 独立审查

名为 `stream-reviewer` 的 Codex agent 在相邻 Herdr 分屏中使用
[review-agent skill](/home/minix/.codex/skills/.system/review-agent/SKILL.md)进行了
审查。它检查了完整未提交 diff 和新文件、相关调用位置、测试、重试边界、异常
兼容性、journal、ATIF 和费用。最终结果为 **No findings（未发现问题）**。它独立
报告：锁定依赖环境下 76 项通过 / 4 项跳过，缓存的 SDK 1.5.0 环境下 80 项通过。
创建 benchmark 分屏前已关闭审查分屏。

## 定向线上实验

所选任务覆盖已提交的历史结果摘要中，所有明确归类为 `RemoteProtocolError` 的
不同任务：

| 任务 | 相关历史尝试 | 历史结果 |
| --- | --- | --- |
| `schemelike-metacircular-eval` | 9 月 14 日，第 18 次请求 | 奖励 0；0/63 子用例；无 `eval.scm` |
| `llm-inference-batching-scheduler` | 9 月 14 日，第 3 次请求 | 奖励 0；模型流中断 |
| `torch-tensor-parallelism` | 9 月 12 日，第 1 次请求 | 无官方分数；流中断，随后 verifier 依赖超时 |

准备的作业：`tb21-stream-recovery-targeted3-20260915`。

- 模型：`openrouter/deepseek/deepseek-v4-flash-0731`。
- 数据集：`terminal-bench/terminal-bench-2-1`，固定为
  `sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a`。
- 保留基线中每题的任务引用和缓存镜像摘要。
- 50 次完整回复，每次回复 65,536 token，并发 2，每题尝试一次，不自动进行
  Harbor 整题重试。
- 每次 agent 运行 3,600 秒，收尾宽限 120 秒，Harbor 外层期限 3,780 秒；原生
  verifier 时限不变。
- SDK 1.5.0、httpx 0.28.1、httpx2 2.12.0、Pydantic 2.13.5。
- 复用缓存的 uv 引导程序和被动 HTTP 录制器；定期堆栈转储仍禁用。线上试验
  不注入传输故障。
- 安装与当前每个包源码文件逐一验证过的 wheel。保留未提交源码快照和文件哈希，
  以便将结果与最终提交比较，同时不声称该快照当时已经提交。

从仓库根目录运行的本地复现命令：

```bash
PYTHONPATH=src benchmarks/harbor/.venv/bin/python \
  jobs/tb21-stream-recovery-targeted3-20260915-record/workflow/run.py
```

Runner 拒绝覆盖现有作业，检查 wheel 和镜像摘要，加载已有端点凭据但不将其写入
报告，并在 `jobs/` 下保存源码清单、原始日志、HTTP 记录、journal、轨迹、检查点
和 verifier 输出。

## 解读限制

恢复修复无法确定上游哪个组件关闭了原连接，也不能证明模型能够解决这些任务。
9 月 12 日的 Scheme 解释器在流失败前仅通过 4/63 子用例。采样、路由、缓存状态
和提供商后端均未受控。本定向实验既不是完整 benchmark 分数，也不是通过率提升
的受控测量。未发生中断的线上运行不会覆盖重试分支。

## 证据位置

- [9 月 12 日结果](../../results/tb21-generation-budget-65536-20260912.json)
- [9 月 14 日结果](../../results/tb21-tool-input-recovery-20260914.json)
- [Journal v3 协议](../../../../docs/dev_docs/zh-CN/event-journal-protocol-v3.md)
- 本地记录：`jobs/tb21-stream-recovery-targeted3-20260915-record/`
- 本地离线回放：上述记录内的 `offline_replay.py` 和 `offline-replay.json`

原始任务/模型数据保留在 Git 忽略的本地作业目录内。双语 CLI 文档、v2/v3 协议
源文及英文版本均已同步。
