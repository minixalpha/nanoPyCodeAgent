# Event Journal 实现协议 v3

> 本文件为中文源；英文版本
> [`../en/event-journal-protocol-v3.md`](../en/event-journal-protocol-v3.md) 由其生成。

v3 使用 `schema_version = 3`。当前 writer 已升级到
[v4](event-journal-protocol-v4.md)，本文保留 v3 的协议定义。
v3 reader 和 ATIF projector 继续兼容 v1、v2；公开轨迹仍为 ATIF-v1.7。
除下述新增事件和投影行为外，
[v2](event-journal-protocol-v2.md) 的其他契约保持有效。

## 模型尝试失败

`model.failed` 结束一次 API 尝试，不宣称收到完整消息或完整用量。必填字段如下：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `model_call_id` | 非空字符串 | 对应 `model.started` 的标识。 |
| `error_type` | 非空字符串 | 原始异常类名。 |
| `message` | 字符串 | 原始异常消息。 |
| `generation_id` | 非空字符串或 null | 响应流打开时取得的服务商响应头。 |
| `duration_ms` | 非负数 | 包含响应流读取的尝试耗时。 |
| `will_retry` | 布尔值 | 是否已安排另一次尝试。 |
| `retry_delay_seconds` | 非负数 | 安排的等待时长；不重试时为零。 |
| `source_timestamp` | RFC 3339 UTC 或 null | 事件时间。 |

捕获到 SDK 或传输错误时写入该事件，包括最终失败。意外异常和用户中断沿用
`model.started` / `run.failed` 的表示。每次重试分配新的 `model_call_id`；
重试不是已完成回复，不消耗轮数预算。重试保留最后一次已提交的对话，绝不执行
中断回复中的工具。`will_retry` 记录安排意图；取消或 Journal 写入失败仍可能
阻止下一次尝试启动。

恢复策略只重试响应体读取错误、读取超时和远端协议错误，等待时间分别为 1 秒和
2 秒。从本轮首次中断开始，超过 300 秒窗口后不再安排新重试。进行中的请求
可以超过这个调度窗口；SDK 超时和外部监督器的截止时间仍是独立限制。响应流
打开前的失败沿用 SDK 的重试，不再叠加外层重试。

## 投影与费用

失败尝试按顺序成为 agent step，保留可见文本增量，设置 `llm_call_count = 1`
和 `extra.incomplete = true`，错误及重试信息写入 `extra`。这些 step 不包含
工具调用或 observation，因为没有执行该回复的工具。后续重试成功可以使 run
正常结束，但不会使此前的失败尝试变为完整。

在读取响应体前取得 generation ID，使收尾阶段也能查询中断生成的费用。已确认
费用计入总额；存在未确认的尝试时，费用总额显式保持不完整。即使账单已经补全，
缺失的 token 用量仍然未知。旧版未完成的模型开始事件沿用原来的投影方式。

包含 `model.failed` 的 v1/v2 记录会被拒绝。旧 reader 拒绝 v3，避免静默丢弃
失败尝试。历史 Journal 不会被改写。
