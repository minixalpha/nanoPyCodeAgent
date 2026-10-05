# Event Journal 实现协议 v4

> 本文件为中文源；英文版本
> [`../en/event-journal-protocol-v4.md`](../en/event-journal-protocol-v4.md) 由其生成。

当前 writer 对所有 run 写入 `schema_version = 4`。Reader 和 ATIF projector
继续兼容 v1、v2、v3；公开轨迹仍为 ATIF-v1.7。除以下变化外，
[v3](event-journal-protocol-v3.md) 的契约保持有效。

## 时间预算终态

`run.completed.payload.outcome` 新增 `time_budget_exhausted`，表示 core 在启动
下一次模型调用或工具调用前、模型返回后或执行期间发现 wall-clock 预算已耗尽。原有 `completed`、
`max_turns_exhausted`、`response_truncated` 的含义保持不变。

配置了时间预算的 headless run 使用单调时钟计算截止时间。检查发生在每次模型
尝试之前，以及同一回复中每一个工具执行之前。一个工具耗尽剩余预算后，后续工具
不会启动。POSIX 主线程中的实时信号定时器会中断正在进行的模型或工具工作；不支持
该定时器、非主线程或已有实时定时器时，显式拒绝配置时间预算。模型回复在期限之后
返回时，即使不再请求工具，也记录时间预算耗尽。模型流被中断时记录不重试的
`model.failed`，错误类型为 `DeadlineExceeded`；被中断工具以带错误的
`tool.completed` 记录。已输出的部分内容不会伪装成完整模型回复。

`run.started` 的可选字段 `time_budget_seconds` 记录配置的正整数秒数；未配置时
为 null。旧 Journal 可以不包含该字段。ATIF 将其保留在
`agent.extra.time_budget_seconds`。

预算耗尽以 `run.completed` 正常收尾，headless 退出码为 `0`，费用补查和轨迹写入
仍会执行；时间预算 run 的费用补查另有共享的 30 秒上限，未补齐费用保持 pending，
随后写出轨迹。ATIF 的 `extra.terminal.status` 为 `completed`，
`extra.terminal.outcome` 为 `time_budget_exhausted`。消费者必须检查 outcome，
不能仅凭 status 推断任务完成。

`model.completed` 保留回复请求的全部工具调用；只有实际执行的工具才有
`tool.started`、`tool.completed` 和对应 ATIF observation。因超时跳过的工具
不产生虚构的执行事件或结果。

## 注入的模型输入

新增 Native Event `input.injected`，记录运行时追加到用户角色消息中的文本输入，
与原始 `user.message` 区分。必填字段如下：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `model_call_id` | 非空字符串 | 即将使用该输入的模型尝试标识，与后续最近的 `model.started` 对应。 |
| `content` | 字符串 | 本次追加的完整文本，不是整个对话或工具结果的副本。 |
| `reason` | 非空字符串 | 注入原因；配置时间预算时使用 `time_budget`，只有轮数预算时使用 `turn_budget`；单次 headless 自动续行使用 `truncation_recovery`。 |
| `source_timestamp` | RFC 3339 UTC 或 null | 注入发生时间。 |

配置时间预算时，每次模型尝试（包括重试）都会将提醒追加到最近的用户消息尾部，
然后在 `model.started` 之前记录该事件。首次提醒追加到任务文本，后续提醒追加到
工具结果之后；重试时追加到同一个消息尾部。系统提示保持不变。每次追加都单独
记录。只有轮数预算时，每次新的回复前追加提醒，传输重试沿用原提醒。剩余 10 次
回复（含即将开始的回复），或剩余时间不大于 `max(180 秒, 总预算 × 15%)` 时，
提醒要求完成并保存必要产物、执行必要验证并总结结束；同时说明最后一次回复中的
工具不会执行。原始用户输入和工具结果
不会在 Journal 中被改写。

ATIF 按 Journal 顺序为每个 `input.injected` 创建一个 `source = "user"` 的
step，`message` 为该提醒文本。这里的 user 表示模型请求中的消息角色；
`extra.injected = true` 明确标识它来自运行时。`extra.model_call_id` 和
`extra.reason` 保留关联与原因。该 step 位于对应模型尝试之前，不合并到工具
observation，也不增加 `llm_call_count`。

`content` 沿用 Journal 字符串持久化上限，发生截断时将相关元数据投影到
`extra.journal_truncation`。关联标识和 `reason` 不受字符串截断影响。

## 有界的截断恢复

Headless run 收到 `stop_reason="max_tokens"` 后，如果原始回合与时间预算尚有
剩余，可以自动继续一次。截断回复仍保留自己的 `model.completed`、usage 和费用。
该回复的工具不会执行；后续请求历史只保留可见文本和截断提示。

恢复时增加一条用户角色消息，并记录 reason 为 `truncation_recovery` 的
`input.injected`，关联下一次模型尝试。在该次 `model.started` 之前还可能追加
预算提醒。传输重试复用恢复消息，不再次注入。成功的工具执行或传输重试都不会
重置每次 run 仅一次的恢复额度。后续再次截断则以 `response_truncated` 结束；
正常完成和预算耗尽仍使用原有 outcome。交互模式在截断后仍返回用户输入。

没有新增事件类型、outcome 或必填字段：`reason` 是开放字符串，因此保持 schema
v4，与已有 reader 兼容。ATIF 保留注入消息与两次模型步骤，包括首次步骤的
`max_tokens` 原因。

## 兼容性与验证

outcome 和事件类型都是封闭枚举，新增值需要递增 schema。v1/v2/v3 记录包含
`time_budget_exhausted` 或 `input.injected` 时必须拒绝；旧 reader 会拒绝 v4。
历史 Journal 不会被改写。既有版本边界保持不变：`response_truncated` 从 v2
开始有效，`model.failed` 从 v3 开始有效。

- [`test_time_budget.py`](../../../tests/test_time_budget.py) 覆盖逐工具截止时间检查，
  以及初始提醒、工具结果后的提醒和最终阶段警告在 Journal/ATIF 中的持久化。
- [`test_truncation.py`](../../../tests/test_truncation.py) 覆盖各版本的 outcome 边界；
  [`test_event_journal.py`](../../../tests/test_event_journal.py) 覆盖注入事件的版本边界。
- [Harbor 兼容性测试](../../../benchmarks/harbor/tests/test_atif_compatibility.py)
  使用固定版本的官方 ATIF validator 验证包含提醒和预算终态的 v4 投影。
