# Pi、Claude Code、Codex、OpenCode 与 Grok 的内部事件如何映射到 ATIF

> 本文件为**中文源文件**（source of truth）；对应英文版应完整生成到 `../en/agent_events_to_atif_examples.md`，当前尚未生成。

调研时间：2026-08-23。

## 问题

> 能不能给一些真实的例子，比如 Pi、Codex、Claude Code、OpenCode、Grok 的 agent 内部事件长什么样，对应的 ATIF 是什么？
>
> 这些 native event 示例为什么没有时间戳？

## 结论先行

可以，但“真实”需要先限定含义。本文分两层证据：前面的“本机实测补充”保留 Pi、Codex、Claude Code 和 OpenCode 四次真实运行的 ID、token 与时间；后面的五组横向示例则依据真实类型定义、转换器和测试做 **schema-faithful 重建**，其中任务内容、ID、token 数和时间值是便于比较的示意值。Grok 因本机未安装，只提供源码重建示例。

五个项目的共同规律是：**agent loop 先产生自身的 message/event/state，ATIF 是之后整理出的评测视图，并不是 loop 内部直接运行的对象模型。** 差异主要在三个地方：

1. 原生事件按模型消息、工具状态还是 CLI item 组织；
2. token/cost 是逐次模型调用提供，还是只在 run/turn 末尾聚合；
3. 时间是事件 envelope 自带、藏在 payload 中，还是只能由接收器补采。

时间戳尤其不能从简化示例反推原始协议。实际情况是：

| Agent | 事件 envelope 的统一时间 | 其他可用时间 | 本文建议的 ATIF 时间来源 |
|---|---|---|---|
| Pi | `AgentEvent` 没有 | session header 和 `AgentMessage.timestamp` 有；持久化 harness entry 另有 storage timestamp | 优先 message timestamp；工具事件由采集器补 receive time |
| Claude Code | SDK stream 没有统一时间 | 本机 2.1.237 的 `assistant`/`user` message 有 ISO timestamp；`system`/`result` 没有，`result` 有 duration | 有 message timestamp 时采用，否则补 receive time |
| Codex `exec --json` | `ThreadEvent` 没有 | 更底层 protocol 的部分对象有 start/end，但公开 `ThreadEvent` 未保留 | 由 JSONL 接收器补 receive time |
| OpenCode | 有 | `message.part.updated.properties.time`，message/tool state 也有 create/start/end | 直接使用原生毫秒时间 |
| Grok `streaming-json` | 没有 | terminal event 有 usage，内部持久化层另有时序信息，但公开 reducer 未输出 | 由 JSONL 接收器补 receive time |

因此 nanoPyCodeAgent 自己的持久化 native event 不应照抄任何一家公开流的缺口。推荐每条记录至少有严格递增的 `seq` 和 UTC `timestamp`：前者负责可靠排序，后者负责跨系统关联和投影 ATIF。墙上时钟可能回拨或让并发事件得到相同时间，不能只靠 timestamp 排序。

## 调研范围

本文以仓库 `references/` 下的固定快照为依据：

- Pi：`c49906ec77788625aacbdc53ebca6fbe65bd20f5`
- Codex：`4f39251a010a8bd7d692d25fb33832ff06f1635a`
- Claude Code 非官方源码快照：`a371abbe75ffa0d0a3c92290e2bbf56a7ef54367`
- OpenCode：`e00890c67261a435cee6409366a68999a93393fd`
- Grok Build：`19d42e35c07a9c9244f03f6df0c4c353f970d4f9`
- Harbor：[`benchmarks/harbor/pyproject.toml`](../../../benchmarks/harbor/pyproject.toml) 固定的 0.21.0，其 trajectory schema 为 ATIF-v1.7

### 本机实测补充

在源码调研之外，本文还于 2026-08-23 实际运行了本机安装的四个 CLI：

| CLI | 版本 | 结果 |
|---|---:|---|
| Pi | 0.84.2 | 成功，`openai-codex/gpt-5.6-sol`，两次模型响应和一次 `read` |
| Codex | 0.149.0 | 成功，两次 command item 状态和一个 agent message |
| Claude Code | 2.1.237 | 成功，两次 Claude Opus message、一次 `Read`，另有辅助 Haiku usage |
| OpenCode | 1.18.21 | 成功，两组 step 和一次 `read` |

为避免把仓库内容发送给外部模型，四次测试均在 `/tmp` 的临时目录中，只读取一个专门创建的无敏感文件：

```text
NANOPY_EVENT_PROBE_20260823
```

使用的等价 prompt 是：

```text
Use the read tool exactly once to read probe.txt. Do not write or modify
anything. Then reply with only the exact file content.
```

下面是从真实 stdout 中抽取的关键记录。Pi 与 Claude Code 的完整行含大量 encrypted reasoning、插件清单等无关字段，故这里展示字段投影；事件名、ID、数值和时间均来自真实运行，不把投影误称为原样抓包。

#### Pi 0.84.2

```jsonl
{"type":"session","version":3,"id":"01a02e3c-e606-7060-baf2-9a1ded866776","timestamp":"2026-08-23T10:48:58.118Z","cwd":"/tmp/nanopy-agent-event-probe.ktOr9V"}
{"type":"message_end","message":{"role":"assistant","model":"gpt-5.6-sol","provider":"openai-codex","responseId":"resp_0f6a0eea8b7401c0016a8ad01c304087d0a882c3eee1686e09","usage":{"input":597,"output":30,"reasoning":10,"totalTokens":627,"cost":{"total":0.0038850000000000004}},"stopReason":"toolUse","timestamp":1787482138161}}
{"type":"tool_execution_start","toolCallId":"call_j2gAtuUWhalLvXqYLKLke6Yk|fc_0f6a0eea8b7401c0016a8ad01e705c87d0a0c8b9b64c05762e","toolName":"read","args":{"path":"probe.txt"}}
{"type":"tool_execution_end","toolCallId":"call_j2gAtuUWhalLvXqYLKLke6Yk|fc_0f6a0eea8b7401c0016a8ad01e705c87d0a0c8b9b64c05762e","toolName":"read","result":{"content":[{"type":"text","text":"NANOPY_EVENT_PROBE_20260823\n"}]},"isError":false}
{"type":"message_end","message":{"role":"assistant","model":"gpt-5.6-sol","provider":"openai-codex","responseId":"resp_0f6a0eea8b7401c0016a8ad01f3c5c87d0910ad017f42f5588","content":[{"type":"text","text":"NANOPY_EVENT_PROBE_20260823"}],"usage":{"input":648,"output":14,"reasoning":0,"totalTokens":662,"cost":{"total":0.00366}},"stopReason":"stop","timestamp":1787482143410}}
```

它直接验证了：tool lifecycle event 没 timestamp，assistant/toolResult payload 有 timestamp；逐 response usage 很完整。Pi 源码的 [`calculateCost`](../../../references/pi/packages/ai/src/models.ts) 使用模型目录费率乘 tokens，所以 `usage.cost` 是 agent 计算值，不能自动视为 provider 实扣。

#### Codex 0.149.0

```jsonl
{"type":"thread.started","thread_id":"01a02e3d-3743-7ac1-8c30-6c7254135573"}
{"type":"turn.started"}
{"type":"item.started","item":{"id":"item_0","type":"command_execution","command":"/usr/bin/zsh -lc 'cat probe.txt'","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_0","type":"command_execution","command":"/usr/bin/zsh -lc 'cat probe.txt'","aggregated_output":"NANOPY_EVENT_PROBE_20260823\n","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"NANOPY_EVENT_PROBE_20260823"}}
{"type":"turn.completed","usage":{"input_tokens":31003,"cached_input_tokens":19968,"cache_write_input_tokens":0,"output_tokens":135,"reasoning_output_tokens":60}}
```

该输出完整印证了两个缺口：没有任何 timestamp，也没有 cost；usage 只在 `turn.completed` 聚合。

#### Claude Code 2.1.237

```jsonl
{"type":"system","subtype":"api_retry","attempt":1,"max_retries":10,"retry_delay_ms":524,"error_status":401,"error":"authentication_failed","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"assistant","message":{"model":"claude-opus-5","id":"msg_011CeKYuCnCMFvi24JSsJLvS","content":[{"type":"tool_use","id":"toolu_01BdirHMfK8eKMQgjDn2z7KA","name":"Read","input":{"file_path":"/tmp/nanopy-agent-event-probe.ktOr9V/probe.txt"}}],"usage":{"input_tokens":2,"cache_creation_input_tokens":2521,"cache_read_input_tokens":1247,"output_tokens":14}},"timestamp":"2026-08-23T10:50:01.254Z","request_id":"req_011CeKYuC24Db1xnVkk2y6Ai","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01BdirHMfK8eKMQgjDn2z7KA","type":"tool_result","content":"1\tNANOPY_EVENT_PROBE_20260823\n2\t"}]},"timestamp":"2026-08-23T10:50:01.307Z","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"assistant","message":{"model":"claude-opus-5","id":"msg_011CeKYuMzLUNjC8x7bv2GJD","content":[{"type":"text","text":"NANOPY_EVENT_PROBE_20260823"}],"usage":{"input_tokens":2,"cache_creation_input_tokens":130,"cache_read_input_tokens":3768,"output_tokens":1}},"timestamp":"2026-08-23T10:50:02.486Z","request_id":"req_011CeKYuMBxrDUiGKVmhMFzJ","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"result","subtype":"success","num_turns":2,"total_cost_usd":0.032467499999999996,"modelUsage":{"claude-haiku-4-5-20251001":{"inputTokens":920,"outputTokens":12,"costUSD":0.00098},"claude-opus-5[1m]":{"inputTokens":4,"outputTokens":98,"cacheReadInputTokens":5015,"cacheCreationInputTokens":2651,"costUSD":0.031487499999999995}},"result":"NANOPY_EVENT_PROBE_20260823","duration_ms":7920,"session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
```

这纠正了固定源码快照与本机新版本之间的差异：2.1.237 的 assistant/user message 已带 timestamp 和 request ID；但 `system.api_retry`、`result` 仍没有统一 timestamp。`result.total_cost_usd` 还包含可见 Opus 回合之外的 Haiku 辅助调用，因此不能只对可见 assistant message 做加法来重建 run 总额。

#### OpenCode 1.18.21

```jsonl
{"type":"step_start","timestamp":1787482258116,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"messageID":"msg_02e3eaf250017z8BF8zCT2CQ3f","type":"step-start"}}
{"type":"tool_use","timestamp":1787482259124,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"type":"tool","tool":"read","callID":"call_Kap3tANM5Uu9U5raX0ogDuYu","state":{"status":"completed","input":{"filePath":"/tmp/nanopy-agent-event-probe.ktOr9V/probe.txt"},"output":"NANOPY_EVENT_PROBE_20260823","time":{"start":1787482259101,"end":1787482259121}},"messageID":"msg_02e3eaf250017z8BF8zCT2CQ3f"}}
{"type":"step_finish","timestamp":1787482259168,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"reason":"tool-calls","messageID":"msg_02e3eaf250017z8BF8zCT2CQ3f","type":"step-finish","tokens":{"total":8011,"input":7952,"output":35,"reasoning":24,"cache":{"write":0,"read":0}},"cost":0}}
{"type":"step_start","timestamp":1787482261701,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"messageID":"msg_02e3ebedc001joGNk0E3u0NSp7","type":"step-start"}}
{"type":"text","timestamp":1787482261701,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"messageID":"msg_02e3ebedc001joGNk0E3u0NSp7","type":"text","text":"NANOPY_EVENT_PROBE_20260823","time":{"start":1787482261684,"end":1787482261691}}}
{"type":"step_finish","timestamp":1787482261701,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"reason":"stop","messageID":"msg_02e3ebedc001joGNk0E3u0NSp7","type":"step-finish","tokens":{"total":8113,"input":397,"output":16,"reasoning":20,"cache":{"write":0,"read":7680}},"cost":0}}
```

OpenCode CLI 并没有把 SDK 内部的 `message.part.updated` 原样打印，而是在 [`run.ts`](../../../references/opencode/packages/opencode/src/cli/cmd/run.ts) 中投影成上述 `step_start/tool_use/step_finish/text`，并在每行用 `Date.now()` 添加顶层 timestamp。本次 `cost: 0` 只能解释为 OpenCode 对当前模型给出的 agent-reported value；没有 provider 账单来源时，不能进一步断言该调用真实免费。

### 实测事件怎样投影 ATIF

四次实测的映射策略如下：

| CLI | ATIF step 边界 | timestamp | step metrics | run cost |
|---|---|---|---|---|
| Pi | 每个 completed assistant message | message Unix ms | 逐 response tokens；本地计算 cost 放 `metrics.extra.estimated_cost_usd` | 不作为真实 `total_cost_usd` |
| Codex | command item step + final message step | receiver 补采 | turn 聚合只能进 `final_metrics` | 缺失 |
| Claude Code | 每个 assistant `message.id` | assistant timestamp | 可见 message usage；prompt tokens 需加 input + cache create + cache read | `result.total_cost_usd` 可作为 agent-reported run cost，并注明含辅助调用 |
| OpenCode | 每个 `messageID`，由 `step_finish` 封口 | CLI 顶层 timestamp | tokens 逐 step；cache 是 prompt 子集 | cost 标明 agent-reported，不能冒充 provider-reported |

以实测 Claude Code 为例，对应的关键 ATIF 不是简单复制 `input_tokens`：ATIF `prompt_tokens` 定义包含 cached 与 non-cached，所以第一次可见 Opus step 是 `2 + 2521 + 1247 = 3770`，第二次是 `2 + 130 + 3768 = 3900`：

```json
{
  "steps": [
    {
      "step_id": 2,
      "timestamp": "2026-08-23T10:50:01.254Z",
      "source": "agent",
      "model_name": "claude-opus-5",
      "message": "",
      "tool_calls": [{"tool_call_id":"toolu_01BdirHMfK8eKMQgjDn2z7KA","function_name":"Read","arguments":{"file_path":"/tmp/nanopy-agent-event-probe.ktOr9V/probe.txt"}}],
      "observation": {"results":[{"source_call_id":"toolu_01BdirHMfK8eKMQgjDn2z7KA","content":"NANOPY_EVENT_PROBE_20260823"}]},
      "metrics": {"prompt_tokens":3770,"completion_tokens":14,"cached_tokens":1247},
      "llm_call_count": 1
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T10:50:02.486Z",
      "source": "agent",
      "model_name": "claude-opus-5",
      "message": "NANOPY_EVENT_PROBE_20260823",
      "metrics": {"prompt_tokens":3900,"completion_tokens":1,"cached_tokens":3768},
      "llm_call_count": 1
    }
  ],
  "final_metrics": {
    "total_prompt_tokens": 8590,
    "total_completion_tokens": 110,
    "total_cached_tokens": 5015,
    "total_cost_usd": 0.032467499999999996,
    "extra": {"cost_source":"claude_code_result","includes_auxiliary_model_calls":true,"auxiliary_model":"claude-haiku-4-5-20251001"}
  }
}
```

这里 `final_metrics` 按 `modelUsage` 汇总了 Opus 与辅助 Haiku，故大于两个可见 step 的 metrics 总和。该差异必须保留说明，不能为了让数字相等而丢掉隐藏调用或把 Haiku tokens 硬分摊给某个可见 step。

为便于比较，五组例子都采用同一个任务：

```text
读取 src/main.rs，然后总结它的作用。
```

下面的 ATIF 片段只展开 `steps` 中与映射有关的字段。完整文档还需要根级 `schema_version`、`agent` 等字段。ATIF-v1.7 的 `Step.timestamp` 是可选 ISO 8601 字符串；本文仍建议 nano 在有可靠来源时总是填写，并在 `extra.timestamp_source` 标明来源。

---

## 一、Pi：围绕 turn、message 和 tool execution 发事件

Pi 的真实 `AgentEvent` 联合类型见 [`packages/agent/src/types.ts`](../../../references/pi/packages/agent/src/types.ts)，JSONL 说明见 [`packages/coding-agent/docs/json.md`](../../../references/pi/packages/coding-agent/docs/json.md)。事件类型包括：

```typescript
type AgentEvent =
  | { type: "agent_start" }
  | { type: "agent_end"; messages: AgentMessage[] }
  | { type: "turn_start" }
  | { type: "turn_end"; message: AgentMessage; toolResults: ToolResultMessage[] }
  | { type: "message_start"; message: AgentMessage }
  | { type: "message_update"; message: AgentMessage; assistantMessageEvent: AssistantMessageEvent }
  | { type: "message_end"; message: AgentMessage }
  | { type: "tool_execution_start"; toolCallId: string; toolName: string; args: any }
  | { type: "tool_execution_update"; toolCallId: string; toolName: string; args: any; partialResult: any }
  | { type: "tool_execution_end"; toolCallId: string; toolName: string; result: any; isError: boolean };
```

### 1.1 原生事件长什么样

下面省略文本 delta，只保留一次工具调用和两次模型响应的权威完成事件：

```jsonl
{"type":"session","version":3,"id":"pi-session-1","timestamp":"2026-08-23T08:00:00.000Z","cwd":"/workspace"}
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"user","content":"读取 src/main.rs，然后总结它的作用。","timestamp":1787472000100}}
{"type":"message_end","message":{"role":"user","content":"读取 src/main.rs，然后总结它的作用。","timestamp":1787472000100}}
{"type":"tool_execution_start","toolCallId":"call_read_1","toolName":"read","args":{"path":"src/main.rs"}}
{"type":"tool_execution_end","toolCallId":"call_read_1","toolName":"read","result":{"content":"fn main() { println!(\"hello\"); }"},"isError":false}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"我先读取入口文件。"},{"type":"toolCall","id":"call_read_1","name":"read","arguments":{"path":"src/main.rs"}}],"api":"anthropic-messages","provider":"anthropic","model":"claude-sonnet-4","usage":{"input":120,"output":24,"cacheRead":0,"cacheWrite":0,"totalTokens":144,"cost":{"input":0.00036,"output":0.00036,"cacheRead":0,"cacheWrite":0,"total":0.00072}},"stopReason":"toolUse","timestamp":1787472001250},"toolResults":[{"role":"toolResult","toolCallId":"call_read_1","toolName":"read","content":[{"type":"text","text":"fn main() { println!(\"hello\"); }"}],"isError":false,"timestamp":1787472001420}]}
{"type":"turn_start"}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"这是一个最小 Rust 程序，main 函数向标准输出打印 hello。"}],"api":"anthropic-messages","provider":"anthropic","model":"claude-sonnet-4","usage":{"input":168,"output":31,"cacheRead":0,"cacheWrite":0,"totalTokens":199,"cost":{"input":0.000504,"output":0.000465,"cacheRead":0,"cacheWrite":0,"total":0.000969}},"stopReason":"stop","timestamp":1787472002100},"toolResults":[]}
```

这里的时间语义是混合的：

- session header 有 ISO timestamp；
- `turn_start`、`tool_execution_start/end` 的 `AgentEvent` envelope 没有 timestamp；
- `UserMessage`、`AssistantMessage` 和 `ToolResultMessage` 的真实类型有 Unix 毫秒 `timestamp`，见 [`packages/ai/src/types.ts`](../../../references/pi/packages/ai/src/types.ts)；
- Pi 新的持久化 harness entry 还有 storage-assigned timestamp，但那是另一层 journal，不是上述 UI event envelope。

### 1.2 对应 ATIF

```json
{
  "steps": [
    {
      "step_id": 1,
      "timestamp": "2026-08-23T08:00:00.100Z",
      "source": "user",
      "message": "读取 src/main.rs，然后总结它的作用。",
      "extra": {"timestamp_source": "user_message"}
    },
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.250Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "我先读取入口文件。",
      "tool_calls": [
        {
          "tool_call_id": "call_read_1",
          "function_name": "read",
          "arguments": {"path": "src/main.rs"}
        }
      ],
      "observation": {
        "results": [
          {
            "source_call_id": "call_read_1",
            "content": "fn main() { println!(\"hello\"); }",
            "extra": {"is_error": false}
          }
        ]
      },
      "metrics": {
        "prompt_tokens": 120,
        "completion_tokens": 24,
        "cached_tokens": 0,
        "extra": {"estimated_cost_usd": 0.00072, "cost_source": "pi_model_catalog"}
      },
      "llm_call_count": 1,
      "extra": {"timestamp_source": "assistant_message"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.100Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "这是一个最小 Rust 程序，main 函数向标准输出打印 hello。",
      "metrics": {
        "prompt_tokens": 168,
        "completion_tokens": 31,
        "cached_tokens": 0,
        "extra": {"estimated_cost_usd": 0.000969, "cost_source": "pi_model_catalog"}
      },
      "llm_call_count": 1,
      "extra": {"timestamp_source": "assistant_message"}
    }
  ]
}
```

Pi 是五者中最接近逐模型调用无损映射的一种：`turn_end.message` 已经有模型、内容、tool call、usage 和 timestamp，`toolResults` 又保留调用关联。其 cost 还需标注来源：当前主流 provider adapter 调用模型目录费率计算，结构完整不等于 provider 实扣。

---

## 二、Claude Code：SDK message stream 需要按 message ID 和 tool_use ID 归并

Claude Code 的 SDK 输出类型见 [`src/entrypoints/sdk/coreSchemas.ts`](../../../references/claude-code/src/entrypoints/sdk/coreSchemas.ts)。Harbor 的 Claude Code adapter 使用 `--output-format=stream-json --print`，再将多行 SDK message 整理为 ATIF。

### 2.1 原生事件长什么样

```jsonl
{"type":"system","subtype":"init","cwd":"/workspace","tools":["Read"],"model":"claude-sonnet-4","permissionMode":"bypassPermissions","uuid":"sys-1","session_id":"claude-session-1","apiKeySource":"ANTHROPIC_API_KEY","mcp_servers":[],"slash_commands":[],"output_style":"default","skills":[],"plugins":[],"claude_code_version":"2.x"}
{"type":"assistant","message":{"id":"msg_tool_1","type":"message","role":"assistant","model":"claude-sonnet-4","content":[{"type":"text","text":"我先读取入口文件。"},{"type":"tool_use","id":"toolu_read_1","name":"Read","input":{"file_path":"/workspace/src/main.rs"}}],"stop_reason":"tool_use","stop_sequence":null,"usage":{"input_tokens":120,"output_tokens":24,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"parent_tool_use_id":null,"uuid":"assistant-1","session_id":"claude-session-1"}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_read_1","content":"fn main() { println!(\"hello\"); }","is_error":false}]},"parent_tool_use_id":null,"tool_use_result":{"type":"text","file":{"filePath":"/workspace/src/main.rs","content":"fn main() { println!(\"hello\"); }"}},"timestamp":"2026-08-23T08:00:01.420Z","uuid":"user-tool-result-1","session_id":"claude-session-1"}
{"type":"assistant","message":{"id":"msg_final_1","type":"message","role":"assistant","model":"claude-sonnet-4","content":[{"type":"text","text":"这是一个最小 Rust 程序，main 函数向标准输出打印 hello。"}],"stop_reason":"end_turn","stop_sequence":null,"usage":{"input_tokens":168,"output_tokens":31,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"parent_tool_use_id":null,"uuid":"assistant-2","session_id":"claude-session-1"}
{"type":"result","subtype":"success","duration_ms":2100,"duration_api_ms":1700,"is_error":false,"num_turns":2,"result":"这是一个最小 Rust 程序，main 函数向标准输出打印 hello。","stop_reason":"end_turn","total_cost_usd":0.001689,"usage":{"input_tokens":288,"output_tokens":55},"modelUsage":{"claude-sonnet-4":{"inputTokens":288,"outputTokens":55,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"costUSD":0.001689,"contextWindow":200000,"maxOutputTokens":64000}},"permission_denials":[],"uuid":"result-1","session_id":"claude-session-1"}
```

SDK stream 没有所有事件统一具备的 timestamp。本机 2.1.237 的 `assistant` 和 `user` message 已有 ISO timestamp，但 `system`、`api_retry` 和 `result` 仍可缺失；固定源码快照中的 `user` timestamp 还是可选字段，并明确要求旧 emitter 缺失时消费者回退到接收时间。

### 2.2 对应 ATIF

```json
{
  "steps": [
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.250Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "我先读取入口文件。",
      "tool_calls": [
        {
          "tool_call_id": "toolu_read_1",
          "function_name": "Read",
          "arguments": {"file_path": "/workspace/src/main.rs"}
        }
      ],
      "observation": {
        "results": [
          {
            "source_call_id": "toolu_read_1",
            "content": "fn main() { println!(\"hello\"); }",
            "extra": {"is_error": false}
          }
        ]
      },
      "metrics": {"prompt_tokens": 120, "completion_tokens": 24, "cached_tokens": 0},
      "llm_call_count": 1,
      "extra": {"native_message_id": "msg_tool_1", "timestamp_source": "assistant_message_or_receiver"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.100Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "这是一个最小 Rust 程序，main 函数向标准输出打印 hello。",
      "metrics": {"prompt_tokens": 168, "completion_tokens": 31, "cached_tokens": 0},
      "llm_call_count": 1,
      "extra": {"native_message_id": "msg_final_1", "timestamp_source": "assistant_message_or_receiver"}
    }
  ],
  "final_metrics": {
    "total_prompt_tokens": 288,
    "total_completion_tokens": 55,
    "total_cached_tokens": 0,
    "total_cost_usd": 0.001689,
    "total_steps": 3,
    "extra": {"cost_source": "claude_code_result", "cost_kind": "agent_reported"}
  }
}
```

映射时有两个关键动作：

1. 以 assistant `message.id` 形成一次模型 step；
2. 以 `tool_result.tool_use_id` 找回此前 `tool_use.id`，把环境结果附到相同 ATIF step 的 `observation`。

`result.total_cost_usd` 是 Claude Code 报告的整个 run 汇总，可能包含辅助模型调用，且不是 Anthropic Messages 响应直接回传的账单字段；不能凭比例伪分摊到两个可见 step。因此上例只写 `final_metrics.total_cost_usd` 并记录来源，不填写逐 step 的 `metrics.cost_usd`。

---

## 三、Codex：公开 JSONL 是 thread/turn/item 投影，usage 只在 turn 末汇总

Codex `exec --json` 的真实事件定义见 [`codex-rs/exec/src/exec_events.rs`](../../../references/codex/codex-rs/exec/src/exec_events.rs)。顶层是 `ThreadEvent`：`thread.started`、`turn.started`、`item.started/updated/completed`、`turn.completed/failed` 和 `error`。

### 3.1 原生事件长什么样

```jsonl
{"type":"thread.started","thread_id":"codex-thread-1"}
{"type":"turn.started"}
{"type":"item.started","item":{"id":"item_cmd_1","type":"command_execution","command":"sed -n '1,200p' src/main.rs","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_cmd_1","type":"command_execution","command":"sed -n '1,200p' src/main.rs","aggregated_output":"fn main() { println!(\"hello\"); }\n","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_msg_1","type":"agent_message","text":"这是一个最小 Rust 程序，main 函数向标准输出打印 hello。"}}
{"type":"turn.completed","usage":{"input_tokens":288,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":55,"reasoning_output_tokens":12}}
```

这些公开 `ThreadEvent` 本身没有 timestamp。Codex 更底层 protocol 的某些 begin/end 对象有 `started_at_ms`、`completed_at_ms`，但 `exec --json` 的规范化事件把它们裁掉了。若 Harbor 只消费 stdout JSONL，就只能在读取每行时补 receive time。

### 3.2 对应 ATIF

```json
{
  "steps": [
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.200Z",
      "source": "agent",
      "message": "",
      "tool_calls": [
        {
          "tool_call_id": "item_cmd_1",
          "function_name": "command_execution",
          "arguments": {"command": "sed -n '1,200p' src/main.rs"}
        }
      ],
      "observation": {
        "results": [
          {
            "source_call_id": "item_cmd_1",
            "content": "fn main() { println!(\"hello\"); }\n",
            "extra": {"exit_code": 0, "status": "completed"}
          }
        ]
      },
      "llm_call_count": 1,
      "extra": {"timestamp_source": "receiver", "usage_attribution": "unavailable"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.050Z",
      "source": "agent",
      "message": "这是一个最小 Rust 程序，main 函数向标准输出打印 hello。",
      "llm_call_count": 1,
      "extra": {"native_item_id": "item_msg_1", "timestamp_source": "receiver", "usage_attribution": "unavailable"}
    }
  ],
  "final_metrics": {
    "total_prompt_tokens": 288,
    "total_completion_tokens": 55,
    "total_cached_tokens": 0,
    "total_steps": 3,
    "extra": {"reasoning_output_tokens": 12}
  }
}
```

这里发生了真实的信息损失：`turn.completed.usage` 覆盖整个用户 turn，其中可能有多次模型推理；公开流没有逐 inference usage，不能可靠地分给 ATIF step 2 和 step 3。正确做法是只填 `final_metrics`，并显式说明 attribution unavailable，而不是平均拆分。

---

## 四、OpenCode：事件更新的是 message part，工具本身是状态机

OpenCode 当前 V2 SDK 类型见 [`packages/sdk/js/src/v2/gen/types.gen.ts`](../../../references/opencode/packages/sdk/js/src/v2/gen/types.gen.ts)，CLI 对这些事件的投影见 [`packages/opencode/src/cli/cmd/run.ts`](../../../references/opencode/packages/opencode/src/cli/cmd/run.ts)。内部核心事件是 `message.part.updated`，part 可以是 text、tool、step-start、step-finish 等；`opencode run --format json` 又把它投影为 `step_start/tool_use/step_finish/text` 并加顶层 timestamp。

### 4.1 原生事件长什么样

```jsonl
{"id":"evt-1","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472001100,"part":{"id":"part-tool-1","sessionID":"oc-session-1","messageID":"msg-1","type":"tool","callID":"call-read-1","tool":"read","state":{"status":"running","input":{"filePath":"src/main.rs"},"title":"Read src/main.rs","metadata":{},"time":{"start":1787472001090}}}}}
{"id":"evt-2","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472001420,"part":{"id":"part-tool-1","sessionID":"oc-session-1","messageID":"msg-1","type":"tool","callID":"call-read-1","tool":"read","state":{"status":"completed","input":{"filePath":"src/main.rs"},"output":"fn main() { println!(\"hello\"); }","title":"Read src/main.rs","metadata":{},"time":{"start":1787472001090,"end":1787472001418}}}}}
{"id":"evt-3","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472001500,"part":{"id":"part-finish-1","sessionID":"oc-session-1","messageID":"msg-1","type":"step-finish","reason":"tool-calls","cost":0.00072,"tokens":{"input":120,"output":24,"reasoning":0,"cache":{"read":0,"write":0}}}}}
{"id":"evt-4","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472002100,"part":{"id":"part-text-2","sessionID":"oc-session-1","messageID":"msg-2","type":"text","text":"这是一个最小 Rust 程序，main 函数向标准输出打印 hello。","time":{"start":1787472001800,"end":1787472002090}}}}
{"id":"evt-5","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472002120,"part":{"id":"part-finish-2","sessionID":"oc-session-1","messageID":"msg-2","type":"step-finish","reason":"stop","cost":0.000969,"tokens":{"input":168,"output":31,"reasoning":0,"cache":{"read":0,"write":0}}}}}
```

此前若把这类示例写成只有 `type` 和 `part`，会错误隐藏一个重要事实：当前 `message.part.updated` 的真实 envelope 有 `properties.time`。此外 assistant message 有 `time.created/completed`，tool state 有 `time.start/end`。

### 4.2 对应 ATIF

```json
{
  "steps": [
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.500Z",
      "source": "agent",
      "message": "",
      "tool_calls": [
        {
          "tool_call_id": "call-read-1",
          "function_name": "read",
          "arguments": {"filePath": "src/main.rs"}
        }
      ],
      "observation": {
        "results": [
          {
            "source_call_id": "call-read-1",
            "content": "fn main() { println!(\"hello\"); }",
            "extra": {"tool_started_at_ms": 1787472001090, "tool_ended_at_ms": 1787472001418}
          }
        ]
      },
      "metrics": {"prompt_tokens": 120, "completion_tokens": 24, "cached_tokens": 0, "extra":{"estimated_cost_usd":0.00072,"cost_source":"opencode_model_catalog"}},
      "llm_call_count": 1,
      "extra": {"native_message_id": "msg-1", "timestamp_source": "event"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.120Z",
      "source": "agent",
      "message": "这是一个最小 Rust 程序，main 函数向标准输出打印 hello。",
      "metrics": {"prompt_tokens": 168, "completion_tokens": 31, "cached_tokens": 0, "extra":{"estimated_cost_usd":0.000969,"cost_source":"opencode_model_catalog"}},
      "llm_call_count": 1,
      "extra": {"native_message_id": "msg-2", "timestamp_source": "event"}
    }
  ]
}
```

转换器必须以 `messageID` 聚合 part，并以 `callID` 关联工具的 running/completed 状态。`step-finish` 提供逐模型 step 的 tokens 和 cost，所以结构上很容易投影；但 OpenCode 当前 cost 是根据模型价格表和 tokens 计算出的值，不等同于 provider 回传的实际扣费凭据。

---

## 五、Grok：`streaming-json` 是从 ACP update 归约出的轻量状态流

Grok 的真实 `streaming-json` wire 定义见 [`xai-grok-pager/src/headless/reducer/acp.rs`](../../../references/grok-build/crates/codegen/xai-grok-pager/src/headless/reducer/acp.rs)，上游统一事件见同目录 [`mod.rs`](../../../references/grok-build/crates/codegen/xai-grok-pager/src/headless/reducer/mod.rs)。它把 ACP update 归约为 `text`、`thought`、`tool_call`、`tool_call_update`、`usage` 和 terminal `end` 等事件。

### 5.1 原生事件长什么样

```jsonl
{"type":"thought","data":"I need to inspect the Rust entry point."}
{"type":"tool_call","toolCallId":"grok-call-1","title":"Read src/main.rs","kind":"read","status":"pending","toolName":"read_file","rawInput":{"path":"src/main.rs"},"content":[],"locations":[{"path":"src/main.rs"}]}
{"type":"tool_call_update","toolCallId":"grok-call-1","status":"completed","content":[{"type":"content","content":{"type":"text","text":"fn main() { println!(\"hello\"); }"}}],"rawOutput":{"text":"fn main() { println!(\"hello\"); }"},"locations":[{"path":"src/main.rs"}]}
{"type":"usage","messageId":"grok-msg-1","stopReason":"tool_use","usage":{"inputTokens":120,"outputTokens":24,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}
{"type":"text","data":"这是一个最小 Rust 程序，main 函数向标准输出打印 hello。"}
{"type":"usage","messageId":"grok-msg-2","stopReason":"end_turn","usage":{"inputTokens":168,"outputTokens":31,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}
{"type":"end","stopReason":"EndTurn","sessionId":"grok-session-1","requestId":"grok-request-1","usage":{"input_tokens":288,"output_tokens":55,"total_tokens":343,"num_turns":2}}
```

`AcpLine` 和 `AcpUsageLine` 都没有 timestamp 字段。事件顺序由 NDJSON 行序给出，terminal `end` 只提供 run 汇总。Grok 内部会维护更多 session/usage 状态，但从 `streaming-json` 接入的第三方不能假定那些内部字段也出现在 stdout。

### 5.2 对应 ATIF

```json
{
  "steps": [
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.500Z",
      "source": "agent",
      "message": "",
      "reasoning_content": "I need to inspect the Rust entry point.",
      "tool_calls": [
        {
          "tool_call_id": "grok-call-1",
          "function_name": "read_file",
          "arguments": {"path": "src/main.rs"}
        }
      ],
      "observation": {
        "results": [
          {"source_call_id": "grok-call-1", "content": "fn main() { println!(\"hello\"); }"}
        ]
      },
      "metrics": {"prompt_tokens": 120, "completion_tokens": 24, "cached_tokens": 0},
      "llm_call_count": 1,
      "extra": {"native_message_id": "grok-msg-1", "timestamp_source": "receiver"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.100Z",
      "source": "agent",
      "message": "这是一个最小 Rust 程序，main 函数向标准输出打印 hello。",
      "metrics": {"prompt_tokens": 168, "completion_tokens": 31, "cached_tokens": 0},
      "llm_call_count": 1,
      "extra": {"native_message_id": "grok-msg-2", "timestamp_source": "receiver"}
    }
  ]
}
```

Grok 的转换是一个小型状态机：累积 thought/text delta；看到 `tool_call` 建立调用；用同一 `toolCallId` 的 `tool_call_update` 完成 observation；最后用 `usage.messageId` 封口一个模型 step。

---

## 六、五种原生结构与 ATIF 的内容差异

从例子可以看到，“原生事件”和 ATIF 并非保存完全不同的事实。二者内容高度重叠，差异在组织方式和完成时机：

| 原生事实 | Pi | Claude Code | Codex | OpenCode | Grok | ATIF 目标 |
|---|---|---|---|---|---|---|
| 模型响应边界 | `turn_end.message` | assistant `message.id` | 未直接暴露，只能从 item/turn 推断 | `messageID` + `step-finish` | `usage.messageId` | 一个 `source: agent` step |
| 工具调用 ID | `toolCallId` | `tool_use.id` | item `id` | `callID` | `toolCallId` | `tool_calls[].tool_call_id` |
| 工具结果 | `toolResults` / execution end | `tool_result` | completed item | completed ToolPart | tool call update | `observation.results[]` |
| 逐调用 token | 有 | 有 | 无，只有 turn 聚合 | 有 | 有 | `step.metrics` |
| 逐调用 cost | 有 agent 计算值，通常非 provider 实扣 | message 无，result 有 agent-reported run 汇总 | 无 | 有 agent 计算值 | 视后端 usage 而定 | 只有来源可靠时写 `step.metrics.cost_usd`，否则进 `extra` |
| 时间 | message 有，event 不统一 | 不统一 | 公开流无 | event/message/tool 均有 | 公开流无 | `step.timestamp`，可选 |

ATIF 是**完成态快照**：它希望每个 step 已经有完整 message、tool calls、observation 和 metrics。原生事件则是**按时间追加的事实**：tool 先 started，后 completed；模型文本可能先 delta，后 completed；cost 甚至可能在 run 后异步补齐。两者可以由同一份事实生成，但不适合用同一个写入 API。

## 七、对 nanoPyCodeAgent 的具体建议

### 7.1 native event 必须自带采集时间和顺序

建议持久化 envelope 采用类似结构：

```json
{
  "schema_version": 1,
  "run_id": "run-123",
  "seq": 17,
  "timestamp": "2026-08-23T08:00:01.420Z",
  "type": "tool.completed",
  "payload": {
    "tool_call_id": "call-read-1",
    "tool_name": "read",
    "result": "fn main() { println!(\"hello\"); }",
    "is_error": false,
    "duration_ms": 330
  }
}
```

语义约束应是：

- `seq` 由 journal 写入器分配，严格递增，是 run 内排序的权威；
- `timestamp` 是事件被 core 接受/写入时的 UTC wall-clock，使用 RFC 3339/ISO 8601；
- 精确耗时使用 `duration_ms` 或成对 start/end 事件，不用两个 wall-clock 相减作为唯一依据；
- 从第三方流导入且没有原生时间时，仍写接收时间，并记录 `timestamp_source: receiver`；
- 不要为缺失时间伪造“模型实际发生时间”。

### 7.2 最小事件集应覆盖模型、工具和 run 终态

建议至少保留：

```text
run.started
user.message
model.started
model.completed
tool.started
tool.completed
run.completed
run.failed
```

其中 `model.completed` 应保留 `message_id`、完整 content/tool calls、实际 model、stop reason、usage 和 provider response/generation ID。这样 ATIF converter 才能做到逐 inference 映射，避免 Codex 公开 JSONL 那种只能拿到 turn 汇总的损失。

### 7.3 不要再设计一套“native trajectory”语义模型

native 层保存上述 append-only events；对外 trajectory 直接投影 ATIF-v1.7。这样只有一份原始事实和一个公开评测格式，不会出现“原生 trajectory schema”与 ATIF 长期双向同步的问题。

这是在看到真实事件与 ATIF 的对应关系后得到的**后续架构建议**，明确取代 [`agent_output_and_trajectory.md`](agent_output_and_trajectory.md) 第 8.4 节中“`--trajectory` 写 native JSONL、adapter 再转 ATIF”的旧建议。旧文档所列 stdout `--output-format` 契约仍然成立；被取代的只是 trajectory 持久格式边界。若 0.8.x 接受本节建议，内部 append-only event journal 不作为另一种公开 trajectory schema，而是恢复和诊断所用的原始事实层。

实现上可以边运行边追加 native JSONL；run 结束或需要 checkpoint 时，将当前事件折叠成完整 ATIF，并用临时文件加原子 rename 更新目标文件。若进程中断，native journal 仍保留到最后一条已落盘事件；ATIF 则保持最后一个完整快照。

## 最终回答

真实项目并没有一种统一的“agent 内部事件”：Pi 是 turn/message/tool event，Claude Code 是 SDK message，Codex 是 thread item，OpenCode 是 message part 状态机，Grok 是 ACP update 的公开归约。ATIF 的作用就是把这些不同形状折叠成统一的 user/agent step、tool call、observation 和 metrics。

此前示例若没有时间戳，不能理解为时间不重要。准确说法是：部分原始 event schema 确实不带统一 timestamp，部分把时间放在 message/tool payload，OpenCode 则直接在 event envelope 带时间。nano 自己实现时应统一补上 `seq + timestamp`，并在投影 ATIF 时记录时间来源；不能依赖 stdout 行序之外的隐含时钟，也不能为了让 ATIF 看起来完整而伪造原生时间。
