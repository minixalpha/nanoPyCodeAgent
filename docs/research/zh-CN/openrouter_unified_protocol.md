# OpenRouter 统一模型协议：能力、Cost 与 nanoPyCodeAgent 接入边界

> 本文件为**中文源文件**（source of truth）；对应英文版应完整生成到 `../en/openrouter_unified_protocol.md`，当前尚未生成。

调研时间：2026-08-23。

## 问题

> OpenRouter 有没有自己模型无关的协议，既直接返回真实 cost，又具备 OpenAI、Anthropic 协议常用的 LLM 与 agent 能力？
>
> 如果有，nanoPyCodeAgent 后续是否应以它作为模型无关的 provider 协议？

## 结论先行

有统一的模型访问表面，但更准确的名称是 **OpenRouter 统一 API**，而不是一套完全独立的“OpenRouter 原生消息协议”。它的主入口是 OpenAI-compatible 的 Chat Completions：

```http
POST https://openrouter.ai/api/v1/chat/completions
```

同一个 request/response 形状可以选择不同厂商的模型；OpenRouter 在其上统一了 provider routing、fallback、usage accounting 等能力。它支持 streaming、tool calling、structured outputs、reasoning、multimodal input 与 prompt caching 等常见功能，但具体模型和 provider 是否支持某项参数仍有差异。

对 nanoPyCodeAgent，建议把它作为后续 **OpenRouter 模型无关 transport 的首选协议**：

1. 默认使用 Chat Completions，而不是继续把 Anthropic Messages 当成 OpenRouter 的通用协议；
2. 非 streaming 完整响应或 streaming 最后一个 SSE event 中直接读取 `usage.cost`；
3. 同时保存 generation ID，必要时用 Generation API 查询或审计真实 cost；
4. 使用 `provider.require_parameters: true`，避免被路由到会忽略必需参数的 provider；
5. OpenRouter Responses API 作为并列候选保留；它的 item/event 模型更丰富，但当前 nano 没有依赖这些额外能力；
6. wire response 只是 Source Record，仍需经过 transport adapter 转成 nano 的 Native Event；它不取代 Event Journal，也不直接等于 ATIF。

## 一、先澄清“OpenRouter 原生协议”这个说法

OpenRouter 的 [FAQ](https://openrouter.ai/docs/faq) 与 [Quickstart](https://openrouter.ai/docs/quickstart) 将 `/api/v1/chat/completions` 描述为 OpenAI-compatible API：可以使用 OpenAI SDK，只需把 base URL 和 API key 指向 OpenRouter；也可以使用 OpenRouter 自己的 SDK。

因此应区分三个概念：

| 概念 | 含义 | 是否适合称为模型无关 |
|---|---|---|
| OpenAI Chat Completions | OpenAI 定义的 messages/choices/tool_calls 基础形状 | 基础协议本身不绑定具体模型 |
| OpenRouter 统一 API | OpenAI-compatible 形状，加上跨模型路由、provider 约束、统一 usage/cost 等 OpenRouter 扩展 | 是，适合作为 nano 的 OpenRouter transport |
| OpenRouter Client SDK | 对上述 HTTP API 的轻量、类型安全封装 | 是客户端实现，不是另一套 wire protocol |
| OpenRouter Agent SDK | 在模型调用之上增加 agent loop、tool execution 和 state management | 是 agent runtime，不是 LLM wire protocol |

所以本文后续使用“OpenRouter 统一 API”或“OpenRouter Chat Completions transport”，不使用容易让人误以为存在第四套全新消息语义的“OpenRouter 原生协议”。nano 的目标是自己实现 agent core，因此即使 OpenRouter Agent SDK 能直接完成 agent loop，也不应让它取代 nano 的 tool loop、Native Event 和 trajectory；若采用官方 SDK，更合适的是薄层 Client SDK。

## 二、三个相关端点的定位

| 端点 | 协议形状 | 状态与能力 | 对 nano 的建议 |
|---|---|---|---|
| `/api/v1/chat/completions` | OpenAI-compatible messages/choices | OpenRouter 主入口；支持 streaming、tools、结构化输出及统一 usage | **作为 OpenRouter 模型无关 transport 的默认选择** |
| `/api/v1/responses` | item/event-oriented Responses | OpenAI-compatible；支持 reasoning、tools、web search，但当前仅支持 stateless 请求 | 作为并列候选评估，不作为本阶段默认 |
| `/api/v1/messages` | Anthropic Messages-compatible | 方便复用 Anthropic SDK 与 content blocks；公开 usage schema 未承诺 `cost` | 作为兼容 transport 保留，不作为 OpenRouter 默认抽象 |

OpenRouter 的 [Chat Completions API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion) 提供 model、messages、tools、tool choice、response format、reasoning、provider routing、fallback models 和 streaming 等参数。

[Responses API](https://openrouter.ai/docs/api/reference/responses/overview) 的数据模型更接近事件/item 流，也支持 reasoning、tool calling 和 web search；但 OpenRouter 当前只支持 stateless 使用，每次请求都要带完整历史，`store: true` 和非空 `previous_response_id` 会被拒绝。它并不缺少 nano agent loop 的基本能力，只是相对 Chat Completions 增加了一套 input/output item 与 streaming event 映射，而 nano 当前没有必须依赖这些额外语义的需求。

选择 Chat Completions 不是因为 Responses “不能做 agent”，而是因为官方 Quickstart 仍把 Chat Completions 作为最直接入口，当前 nano 的 message/tool loop 也更接近它。实现 transport interface 时应避免把 `choices[]` 固化进 core，以便未来增加 Responses adapter，而不必再次改写 Native Event。

[Anthropic Messages endpoint](https://openrouter.ai/docs/api/api-reference/anthropic-messages/create-messages) 则是兼容表面。它让当前 nano 几乎不改 agent loop 就能访问 OpenRouter，但也使 OpenRouter 自己的扩展字段受 Anthropic response schema 约束；cost 就是当前最明显的例子。

## 三、Chat Completions 覆盖哪些 agent 基本能力

### 3.1 多轮消息与 streaming

请求通过 `messages` 传入完整的 user/assistant/tool 历史；`stream: true` 时响应使用 SSE。普通文本位于增量 `delta.content`，工具调用位于增量 `delta.tool_calls`。

transport 必须先按 choice index、tool-call index 和 call ID 组装增量，得到完整的工具名与 JSON arguments 后才能执行工具。不能把单个 SSE frame 当成完整 Tool Call Native Event。

### 3.2 Tool calling

OpenRouter 的 [Tool Calling](https://openrouter.ai/docs/guides/features/tool-calling) 使用 OpenAI function-calling 形状：

- request 在 `tools[].function` 中声明 name、description 和 JSON Schema；
- assistant 通过 `message.tool_calls[]` 发起调用；
- client 执行本地工具；
- 下一次 request 用 `role: "tool"` 和 `tool_call_id` 回传结果；
- 支持 `tool_choice`，部分模型支持并行 tool calls。

“协议支持 tools”不等于“每个模型都支持 tools”。模型目录会声明支持的参数，routing 时还应要求 provider 实际支持这些参数。

### 3.3 Structured outputs

[Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) 使用 `response_format.type = "json_schema"` 和 JSON Schema 约束输出，可与 streaming 组合。模型支持情况并不一致；如果任务依赖严格 schema，应配合：

```json
{
  "provider": {
    "require_parameters": true
  }
}
```

OpenRouter 的 [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection) 说明，默认情况下 provider 可能忽略其不支持的可选参数；`require_parameters` 会把候选范围限制为支持请求参数的 provider。这对 tool calling 和 structured output 的可移植性很重要。

### 3.4 Reasoning、multimodal 与 caching

OpenRouter 还提供：

- [Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)：统一一部分 reasoning 控制与返回字段；不同模型是否暴露 reasoning 内容仍有差异；
- [Multimodal requests](https://openrouter.ai/docs/guides/overview/multimodal/overview)：图片等内容继续通过 Chat Completions 的 messages/content blocks 发送；
- [Prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)：在支持的模型/provider 上统一 cache accounting，但自动缓存、显式断点与 TTL 能力并非完全相同；
- model/provider fallback：OpenRouter 可以在候选模型或 provider 之间路由，最终 response 的 model 与 generation metadata 才是本次调用的实际结果。

所以“模型无关”应理解为 **同一个基础 request/response contract 可以访问多模型**，而不是所有模型的能力、参数语义和质量完全一致。

## 四、一次真实形状的 tool-call 往返

下面的 ID、tokens 与金额是说明性值，但字段形状对应 OpenRouter Chat Completions、Tool Calling 和 Usage Accounting 文档。

### 4.1 首次请求

```http
POST /api/v1/chat/completions
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "anthropic/claude-sonnet-4",
  "messages": [
    {
      "role": "user",
      "content": "读取 pyproject.toml 并告诉我项目名"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {"type": "string"}
          },
          "required": ["path"],
          "additionalProperties": false
        }
      }
    }
  ],
  "tool_choice": "auto",
  "provider": {
    "require_parameters": true
  },
  "stream": false
}
```

### 4.2 模型请求调用工具

```json
{
  "id": "gen-abc123",
  "model": "anthropic/claude-sonnet-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_read_1",
            "type": "function",
            "function": {
              "name": "read_file",
              "arguments": "{\"path\":\"pyproject.toml\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 205,
    "completion_tokens": 18,
    "total_tokens": 223,
    "cost": 0.00071,
    "cost_details": {
      "upstream_inference_cost": 0.00066
    }
  }
}
```

`usage.cost` 表示 OpenRouter 向当前账户收取的本次总额；它不是 nano 根据公开价格表自行计算的估值。

### 4.3 执行工具并继续请求

client 本地执行 `read_file` 后，把原 assistant tool call 和 tool result 都放回消息历史：

```json
{
  "model": "anthropic/claude-sonnet-4",
  "messages": [
    {
      "role": "user",
      "content": "读取 pyproject.toml 并告诉我项目名"
    },
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_read_1",
          "type": "function",
          "function": {
            "name": "read_file",
            "arguments": "{\"path\":\"pyproject.toml\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_read_1",
      "content": "[project]\nname = \"nanoPyCodeAgent\""
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {"type": "string"}
          },
          "required": ["path"],
          "additionalProperties": false
        }
      }
    }
  ],
  "provider": {
    "require_parameters": true
  }
}
```

最终响应的 `choices[0].message.content` 是给用户的文字答案，并再次带本次 model call 自己的 usage/cost。一次 agent turn 可能包含多次 model call，因此 run cost 应对每次实际调用分别记账，再在完整性已知时汇总。

## 五、Cost：直接返回、streaming 与 Generation API

OpenRouter 的 [Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting) 说明，每个完整响应都会包含详细 usage：包括 prompt/completion/reasoning/cache tokens、总 cost 和 cost details。

### 5.1 非 streaming

直接读取完整 JSON response 的：

```text
usage.cost
usage.cost_details.upstream_inference_cost
```

对普通 OpenRouter credits 调用，`usage.cost` 是 nano 应采用的 provider-reported amount。`upstream_inference_cost` 是 provider 成本明细，不应代替向 OpenRouter 账户实际收取的总额。

OpenRouter [FAQ](https://openrouter.ai/docs/faq) 说明其 credits 的基础货币是美元，站点和 API 的定价也以美元表示。因此普通 credits 调用的 `usage.cost` 可以映射到 ATIF `cost_usd`；Native Event 仍应显式保存 `currency: "USD"` 和字段来源，避免仅凭字段名猜测币种。

### 5.2 Streaming

`usage` 位于最后一个 SSE event。transport 必须消费到 terminal event，才能把一次 model call 标成 cost resolved。提前断流时不能把 cost 写成 `0`；应保留 unknown/pending 状态和 generation ID。

旧的：

```json
{"usage": {"include": true}}
```

以及：

```json
{"stream_options": {"include_usage": true}}
```

已经不再是取得 usage 的必要条件；官方文档将它们标为 deprecated/no effect。

### 5.3 Generation API 是 fallback 与审计路径

即使主路径直接收到 `usage.cost`，仍应保存 response header `X-Generation-Id` 或等价 generation ID。遇到以下情况时，通过：

```http
GET /api/v1/generation?id=<generation-id>
```

查询 `data.total_cost`：

- 当前走的是 Anthropic Messages compatibility endpoint，response body 没有 cost；
- streaming 在最终 usage event 前断开；
- 需要核对路由后的实际 model/provider；
- 需要离线补账或审计。

具体记账与 ATIF 映射见 [OpenRouter 的真实 Cost、价格 API 与 Trajectory 记账方案](openrouter_cost_accounting.md)。模型目录的价格字段只适合预算和显式估算，不应覆盖 provider-reported cost。

## 六、OpenRouter wire event 与 nano 内部事件的关系

统一 API 解决的是 **provider transport**，不是 trajectory 存储。建议的数据流是：

```text
OpenRouter HTTP response / SSE frames
              │
              │ Source Records
              ▼
OpenRouter Chat transport
  - assemble content deltas
  - assemble tool-call arguments
  - normalize usage / cost / errors
              │
              │ Native Events
              ▼
        journal writer
              │
              │ Journal Entries
              ▼
         Event Journal
              │
              ▼
        ATIF projector
              │
              ▼
       ATIF Trajectory
```

对应关系如下：

| OpenRouter 数据 | nano 概念 | 原因 |
|---|---|---|
| 原始 JSON response、response headers、单个 SSE frame | Source Record | 是外部协议的原始观察，不是 core 领域事件 |
| 已完整组装的 assistant output | `model.completed` Native Event | core 已理解为一次模型调用完成 |
| 已完整组装的 `tool_calls[]` | `model.completed.payload.tool_calls` | 作为模型完成事实的一部分；必须先合并 streaming arguments，再执行工具 |
| `usage.cost` | `model.completed` 中已 resolved 的 provider-reported cost | cost 与本次 model call 同时到达 |
| Generation API 后补的 `total_cost` | `model.cost_resolved` Native Event | cost 晚到，用 append-only 事件补充，不改写旧 Journal Entry |
| journal writer 添加的 `run_id`、`seq`、`recorded_at` | Journal Entry 的持久化元数据 | 属于完整 Journal Entry，但不属于 OpenRouter 协议 |

因此不应把 OpenRouter JSONL/SSE 原样命名为“native trajectory”，也不应让 ATIF serializer 直接理解所有 provider wire shapes。transport adapter 负责协议差异；Native Event、Event Journal 和 ATIF 的语义边界保持不变。

## 七、nano 当前并不能只改 base URL

当前仓库的 transport 与 Anthropic SDK 紧密耦合：

- [`agent.py`](../../../src/nanopycodeagent/agent.py) 直接创建 `anthropic.Anthropic` 并调用 `client.messages.stream(...)`；
- conversation history 使用 `anthropic.types.MessageParam`；
- tool call/result 使用 `ToolUseBlock` 与 `ToolResultBlockParam`；
- 四个工具定义都标注为 `anthropic.types.ToolParam`；
- tests 中的 fake client 和异常类型也模拟 Anthropic Messages。

OpenRouter Chat Completions 的 tool declaration 很接近现有 JSON Schema，但 assistant tool calls、tool results、streaming delta 和 finish reason 的形状不同。因此迁移不是把 `ANTHROPIC_BASE_URL` 换成另一个 URL，而是要抽出 transport 边界。

### 7.1 建议的最小实现顺序

1. 定义 provider-neutral 的内部 message、content、tool call、tool result 和 usage 类型；
2. 把现有逻辑包进 `AnthropicMessagesTransport`，保持兼容行为；
3. 新增 `OpenRouterChatTransport`，负责 Chat Completions request/response 和 SSE 组装；
4. 两个 transport 都只向 core 产出统一 Native Events；
5. OpenRouter transport 优先读取 `usage.cost`，缺失时交给 generation cost resolver；
6. agent loop 继续负责工具调度，不直接依赖任一 SDK 的 block class；
7. 测试文本 streaming、碎片化 tool arguments、多个 tool calls、usage/cost、reasoning/cache token、提前断流与 API error。

这层抽象的目标是统一 **core 看见的语义**，不是强行抹平所有 provider 功能。provider-specific extensions 可以保留在 Source Record 或 Native Event 的 namespaced `extra` 中。

## 八、建议形成的架构决策

后续实现模型无关协议时，采用以下决策：

1. **OpenRouter 默认协议：** `/api/v1/chat/completions`；
2. **OpenRouter cost 主来源：** response/final SSE event 的 `usage.cost`；
3. **cost fallback：** generation ID + `/api/v1/generation` 的 `total_cost`；
4. **能力约束：** tool calling、structured outputs 等必需能力配合 `provider.require_parameters: true`；
5. **兼容路径：** Anthropic Messages 作为独立 transport 保留，不再代表 core 的内部消息模型；
6. **并列候选：** Responses API 暂不成为默认 transport；待 nano 需要 richer item/event、web search 或 Responses SDK 兼容时再实现 adapter；
7. **存储边界：** wire response 是 Source Record，Native Event/Journal Entry/Event Journal 仍是 nano 自己的运行事实层；
8. **导出边界：** ATIF 继续由 Event Journal 投影，不直接从任一 provider response 拼装。

## 九、本次调研的验证范围

本文的协议结论来自 2026-08-23 的 OpenRouter 官方 API reference、feature guides 与 usage accounting 文档，并结合当前 nano 源码做了静态接入分析。本次没有发起会产生 OpenRouter 费用的线上请求，因此示例中的 ID、token 数与金额是说明性值，不是本项目账户的真实账单记录。

这不影响协议字段与架构决策，但实际实现时仍应增加一个使用最便宜可用模型的 opt-in live integration test，验证当前账户下的：

- non-streaming `usage.cost`；
- streaming terminal usage event；
- `X-Generation-Id` 与 Generation API 对账；
- tool-call delta 组装；
- fallback 后 response model/provider 与 cost 的一致性。
