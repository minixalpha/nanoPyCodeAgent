# Event Journal 实现协议 v2

> 本文件为**中文源文件**（source of truth）；英文版
> [`../en/event-journal-protocol-v2.md`](../en/event-journal-protocol-v2.md) 由其生成。

v2 已实现，是当前 writer 使用的内部 Journal 协议，`schema_version = 2`。
本文完整定义相对 [v1](event-journal-protocol-v1.md) 的变化；未列出的 envelope、
事件类型、字段、校验、排序、持久化与投影规则沿用 v1。公开 trajectory 仍为 ATIF-v1.7。

## 回复截断终态

`run.completed.payload.outcome` 的允许值为：

| 值 | 含义 |
| --- | --- |
| `completed` | 模型结束回复；不代表任务通过 verifier。 |
| `max_turns_exhausted` | 最后一轮仍请求工具，已无下一轮预算，不执行这些工具。 |
| `response_truncated` | 模型返回 `stop_reason="max_tokens"`，本次生成达到长度上限，run 停止。 |

`model.completed` 表示一次 API 调用已返回最终消息与 usage，不保证模型完成了回复。
截断回复仍产生该事件，保留 `stop_reason="max_tokens"`、原始 content、tool calls、
usage 和已有 provider 标识。正常费用补查仍在 run 收尾时执行。

core 在检查轮数上限和执行工具之前识别截断，即使该回复恰好用尽最后一轮，也记录
`response_truncated`。该回复中的工具一律不执行，不产生 `tool.started` 或
`tool.completed`，也不伪造 observation。已有文本继续保留在 stdout，截断提示写入
stderr；headless 退出码为 `0`。当前策略是停止，不自动续写、重试或增大 8192 上限。

这属于有明确原因的预算终态，使用 `run.completed`，而非 `run.failed`。
ATIF 的 `extra.terminal.status` 仍为 `completed`，表示 run 已正常收尾；
`extra.terminal.outcome = "response_truncated"` 才是具体结果。
对应模型 step 的 `extra.stop_reason` 为 `max_tokens`。消费者判断是否截断时必须
读取 outcome，不能仅凭 status 推断任务完成。

交互模式返回输入提示符。供下一次请求使用的会话历史仅保留该回复的 text 与明确的
截断提示，移除未执行的工具调用和可能未完成的 thinking 等非文本 block，避免下一次
请求携带无对应结果的工具调用或不完整签名。原始模型回复仍按 Journal 持久化规则保存；
该历史修整不改写运行事实，不产生虚构的工具执行事件。

## 兼容性

- v1 的 outcome 枚举是封闭的，新增值需要提升 schema，而不是作为 v1 可选扩展。
- 新 writer 对所有 run 写入 `schema_version = 2`；新 reader/replay 与 ATIF projector
  同时支持 v1 和 v2。已有 v1 Journal 不改写，历史 `completed` 也不会被追溯重分类。
- v1 记录中出现 `response_truncated` 会被拒绝；旧 reader 会明确拒绝 v2 schema。
- 其他未知 schema 仍被拒绝；v1 的其余兼容性规则继续适用。
- Journal 字符串持久化截断的顶层 `truncation` 字段保持原义，与模型生成长度上限
  是两个独立概念。

## 实现与验证

- [`agent.py`](../../../src/nanopycodeagent/agent.py)：显式 RunOutcome、截断停止、
  文本提示与交互历史处理。
- [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py)：v2 writer、v1/v2
  replay 与 outcome 校验。
- [`atif.py`](../../../src/nanopycodeagent/atif.py)：两种 Journal 版本到 ATIF-v1.7 的投影。
- [`test_truncation.py`](../../../tests/test_truncation.py)：文本、thinking、空回复、部分
  工具 JSON、最后一轮、费用、轨迹与交互下一轮。
- [Harbor 兼容性测试](../../../benchmarks/harbor/tests/test_atif_compatibility.py)：
  旧 v1 fixture 与新 v2 截断轨迹通过固定版本的官方 ATIF validator。
