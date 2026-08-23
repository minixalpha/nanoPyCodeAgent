# OpenRouter's Unified Model Protocol: Capabilities, Cost, and the nanoPyCodeAgent Integration Boundary

> Generated from the Chinese source [`../zh-CN/openrouter_unified_protocol.md`](../zh-CN/openrouter_unified_protocol.md). Do not edit by hand.

Surveyed on 2026-08-23.

## Question

> Does OpenRouter have its own model-independent protocol that both returns actual cost directly and provides the LLM and agent capabilities commonly used through the OpenAI and Anthropic protocols?
>
> If so, should nanoPyCodeAgent use it as its model-independent provider protocol going forward?

## Conclusions first

OpenRouter does provide a unified model-access surface, but the more accurate name is the **OpenRouter unified API**, not a completely separate “native OpenRouter messaging protocol.” Its primary entry point is the OpenAI-compatible Chat Completions endpoint:

```http
POST https://openrouter.ai/api/v1/chat/completions
```

The same request and response shape can select models from different vendors, while OpenRouter adds unified provider routing, fallback, usage accounting, and related capabilities. It supports familiar features including streaming, tool calling, structured outputs, reasoning, multimodal input, and prompt caching, though individual models and providers still differ in which parameters they support.

For nanoPyCodeAgent, this should become the preferred protocol for a future **model-independent OpenRouter transport**:

1. Use Chat Completions by default rather than continuing to treat Anthropic Messages as OpenRouter's general-purpose protocol.
2. Read `usage.cost` directly from a complete non-streaming response or the final SSE event of a streaming response.
3. Preserve the generation ID as well, using the Generation API to retrieve or audit actual cost when necessary.
4. Set `provider.require_parameters: true` to avoid routing to a provider that would ignore required parameters.
5. Keep the OpenRouter Responses API as a peer candidate. Its item/event model is richer, but nano does not currently depend on those additional capabilities.
6. Treat the wire response as a Source Record that a transport adapter must convert into nano Native Events. It neither replaces the Event Journal nor directly equals ATIF.

## 1. First, clarify the phrase “native OpenRouter protocol”

OpenRouter's [FAQ](https://openrouter.ai/docs/faq) and [Quickstart](https://openrouter.ai/docs/quickstart) describe `/api/v1/chat/completions` as an OpenAI-compatible API. An OpenAI SDK can be used by pointing its base URL and API key at OpenRouter; OpenRouter's own SDK is another option.

The following concepts should therefore remain distinct:

| Concept | Meaning | Model-independent? |
|---|---|---|
| OpenAI Chat Completions | The base messages/choices/tool_calls shape defined by OpenAI | The base protocol itself is not tied to one model |
| OpenRouter unified API | An OpenAI-compatible shape plus OpenRouter extensions for cross-model routing, provider constraints, unified usage/cost, and more | Yes; suitable as nano's OpenRouter transport |
| OpenRouter Client SDK | A lightweight, type-safe wrapper around that HTTP API | It is a client implementation, not another wire protocol |
| OpenRouter Agent SDK | Agent loop, tool execution, and state management layered above model calls | It is an agent runtime, not an LLM wire protocol |

The rest of this document therefore uses “OpenRouter unified API” or “OpenRouter Chat Completions transport,” avoiding “native OpenRouter protocol,” which could incorrectly suggest a fourth, wholly new set of message semantics. nano's purpose is to implement its own agent core. Even if the OpenRouter Agent SDK can provide an agent loop directly, it should not replace nano's tool loop, Native Events, or trajectory. If an official SDK is adopted, the thin Client SDK is the better fit.

## 2. Roles of the three relevant endpoints

| Endpoint | Protocol shape | Status and capabilities | Recommendation for nano |
|---|---|---|---|
| `/api/v1/chat/completions` | OpenAI-compatible messages/choices | OpenRouter's main entry point; supports streaming, tools, structured output, and unified usage | **Default for a model-independent OpenRouter transport** |
| `/api/v1/responses` | Item/event-oriented Responses | OpenAI-compatible; supports reasoning, tools, and web search, but currently only stateless requests | Evaluate as a peer candidate, not the default for this phase |
| `/api/v1/messages` | Anthropic Messages-compatible | Convenient for reusing the Anthropic SDK and content blocks; the public usage schema does not promise `cost` | Retain as a compatibility transport, not the default OpenRouter abstraction |

OpenRouter's [Chat Completions API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion) supports model, messages, tools, tool choice, response format, reasoning, provider routing, fallback models, streaming, and other parameters.

The [Responses API](https://openrouter.ai/docs/api/reference/responses/overview) uses a data model closer to an event/item stream and also supports reasoning, tool calling, and web search. OpenRouter currently supports it only in stateless form: every request must carry the full history, and `store: true` or a non-empty `previous_response_id` is rejected. It does not lack the basic capabilities needed by nano's agent loop; it merely adds another input/output item and streaming-event mapping that nano does not currently require.

Chat Completions is the preferred choice not because Responses “cannot build an agent,” but because the official Quickstart still presents Chat Completions as the most direct entry point and nano's current message/tool loop is closer to that shape. A transport interface should avoid embedding `choices[]` into core so a Responses adapter can be added later without rewriting Native Events again.

The [Anthropic Messages endpoint](https://openrouter.ai/docs/api/api-reference/anthropic-messages/create-messages) is a compatibility surface. It allows the current nano agent loop to access OpenRouter with almost no changes, but it also constrains OpenRouter-specific extensions to the Anthropic response schema. Cost is the clearest current example.

## 3. Agent fundamentals covered by Chat Completions

### 3.1 Multi-turn messages and streaming

A request sends the complete user/assistant/tool history through `messages`. With `stream: true`, the response uses SSE. Ordinary text appears in incremental `delta.content`, while tool calls appear in incremental `delta.tool_calls`.

The transport must assemble these increments by choice index, tool-call index, and call ID, producing a complete tool name and JSON arguments before executing the tool. A single SSE frame must not be treated as a complete Tool Call Native Event.

### 3.2 Tool calling

OpenRouter's [Tool Calling](https://openrouter.ai/docs/guides/features/tool-calling) uses the OpenAI function-calling shape:

- The request declares a name, description, and JSON Schema under `tools[].function`.
- The assistant requests calls through `message.tool_calls[]`.
- The client executes local tools.
- The next request returns each result with `role: "tool"` and `tool_call_id`.
- `tool_choice` is supported, and some models support parallel tool calls.

“The protocol supports tools” does not mean “every model supports tools.” The model catalog declares supported parameters, and routing should require the selected provider to support parameters on which the task depends.

### 3.3 Structured outputs

[Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) uses `response_format.type = "json_schema"` with a JSON Schema constraint and can be combined with streaming. Model support varies. If a task depends on a strict schema, pair it with:

```json
{
  "provider": {
    "require_parameters": true
  }
}
```

OpenRouter's [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection) documentation explains that providers may otherwise ignore optional parameters they do not support. `require_parameters` restricts candidates to providers that support the requested parameters, which matters for portable tool calling and structured output.

### 3.4 Reasoning, multimodal input, and caching

OpenRouter also provides:

- [Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens): a partially unified set of controls and response fields for reasoning; models still vary in whether they expose reasoning content.
- [Multimodal requests](https://openrouter.ai/docs/guides/overview/multimodal/overview): images and other content continue to travel in Chat Completions messages/content blocks.
- [Prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching): unified cache accounting across supported models and providers, though automatic caching, explicit breakpoints, and TTL capabilities are not identical.
- Model and provider fallback: OpenRouter can route among candidate models or providers; the final response model and generation metadata are the actual result for that call.

“Model-independent” therefore means that **one base request/response contract can access multiple models**, not that every model has identical capabilities, parameter semantics, or quality.

## 4. A realistically shaped tool-call round trip

The IDs, token counts, and amounts below are illustrative, but the field shapes follow the OpenRouter Chat Completions, Tool Calling, and Usage Accounting documentation.

### 4.1 Initial request

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
      "content": "Read pyproject.toml and tell me the project name"
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

### 4.2 The model requests a tool call

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

`usage.cost` is the total OpenRouter charged the current account for this call; it is not an estimate nano calculated from a public price catalog.

### 4.3 Execute the tool and continue the request

After the client executes `read_file` locally, it places both the original assistant tool call and the tool result back into the message history:

```json
{
  "model": "anthropic/claude-sonnet-4",
  "messages": [
    {
      "role": "user",
      "content": "Read pyproject.toml and tell me the project name"
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

The final response's `choices[0].message.content` is the textual answer for the user and again carries usage/cost for that model call. One agent turn may contain multiple model calls, so run cost must account for each actual call separately and sum them only when completeness is known.

## 5. Cost: direct responses, streaming, and the Generation API

OpenRouter's [Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting) documentation says every complete response contains detailed usage, including prompt, completion, reasoning, and cache tokens, total cost, and cost details.

### 5.1 Non-streaming

Read these fields directly from the complete JSON response:

```text
usage.cost
usage.cost_details.upstream_inference_cost
```

For ordinary OpenRouter credits calls, `usage.cost` is the provider-reported amount nano should use. `upstream_inference_cost` is provider cost detail and must not replace the total actually charged to the OpenRouter account.

OpenRouter's [FAQ](https://openrouter.ai/docs/faq) says its credits use US dollars as their base currency and that site and API prices are denominated in dollars. `usage.cost` from ordinary credits calls can therefore map to ATIF `cost_usd`. Native Events should still explicitly preserve `currency: "USD"` and the field source rather than inferring currency from the target field name.

### 5.2 Streaming

`usage` appears in the final SSE event. The transport must consume through the terminal event before marking a model call's cost resolved. If a stream ends early, cost must not become `0`; retain an unknown or pending state and the generation ID.

The old:

```json
{"usage": {"include": true}}
```

and:

```json
{"stream_options": {"include_usage": true}}
```

are no longer required to obtain usage; the official documentation marks them deprecated or without effect.

### 5.3 The Generation API is a fallback and audit path

Even when the main path receives `usage.cost` directly, preserve the response header `X-Generation-Id` or an equivalent generation ID. Query `data.total_cost` through:

```http
GET /api/v1/generation?id=<generation-id>
```

when:

- the Anthropic Messages compatibility endpoint is in use and the response body contains no cost;
- streaming disconnects before the final usage event;
- the actual routed model or provider needs to be verified;
- offline cost reconciliation or audit is needed.

See [OpenRouter Actual Cost, Pricing APIs, and Trajectory Accounting](openrouter_cost_accounting.md) for detailed accounting and ATIF mapping. Price fields from the model catalog are suitable only for budgets and explicitly labeled estimates; they must not overwrite provider-reported cost.

## 6. Relationship between OpenRouter wire events and nano internal events

The unified API solves the **provider transport** problem, not trajectory storage. The recommended data flow is:

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

The mapping is:

| OpenRouter data | nano concept | Reason |
|---|---|---|
| Raw JSON response, response headers, or one SSE frame | Source Record | It is a raw observation from an external protocol, not a core domain event |
| Fully assembled assistant output | `model.completed` Native Event | Core now understands that one model call has completed |
| Fully assembled `tool_calls[]` | `model.completed.payload.tool_calls` | Part of the model-completion fact; streaming arguments must be assembled before any tool executes |
| `usage.cost` | Resolved provider-reported cost in `model.completed` | Cost arrives with the model call |
| `total_cost` retrieved later from the Generation API | `model.cost_resolved` Native Event | Cost arrives late, so an append-only event supplements rather than rewrites an old Journal Entry |
| `run_id`, `seq`, and `recorded_at` added by the journal writer | Journal Entry persistence metadata | Part of a complete Journal Entry, not part of the OpenRouter protocol |

OpenRouter JSONL/SSE should therefore not be renamed “native trajectory,” and the ATIF serializer should not directly understand every provider wire shape. The transport adapter owns protocol differences; the semantic boundaries among Native Events, the Event Journal, and ATIF remain stable.

## 7. nano cannot currently switch by changing only the base URL

The current repository is tightly coupled to the Anthropic SDK transport:

- [`agent.py`](../../../src/nanopycodeagent/agent.py) directly creates `anthropic.Anthropic` and calls `client.messages.stream(...)`.
- Conversation history uses `anthropic.types.MessageParam`.
- Tool calls and results use `ToolUseBlock` and `ToolResultBlockParam`.
- All four tool definitions are typed as `anthropic.types.ToolParam`.
- Test fake clients and exception types also model Anthropic Messages.

OpenRouter Chat Completions tool declarations are close to the existing JSON Schemas, but assistant tool calls, tool results, streaming deltas, and finish reasons have different shapes. Migration is therefore not a matter of changing `ANTHROPIC_BASE_URL`; it requires extracting a transport boundary.

### 7.1 Recommended minimum implementation sequence

1. Define provider-neutral internal message, content, tool-call, tool-result, and usage types.
2. Wrap the existing logic in `AnthropicMessagesTransport` without changing behavior.
3. Add `OpenRouterChatTransport` to assemble Chat Completions requests, responses, and SSE streams.
4. Have both transports emit only the same Native Events to core.
5. Let the OpenRouter transport prefer `usage.cost` and delegate to the generation cost resolver when it is missing.
6. Keep tool scheduling in the agent loop without directly depending on either SDK's block classes.
7. Test text streaming, fragmented tool arguments, multiple tool calls, usage/cost, reasoning and cache tokens, early disconnects, and API errors.

The purpose of this abstraction is to unify the **semantics visible to core**, not to erase all provider-specific functionality. Provider extensions can remain in Source Records or a namespaced `extra` field on Native Events.

## 8. Recommended architecture decision

Adopt the following decisions when implementing a model-independent protocol:

1. **Default OpenRouter protocol:** `/api/v1/chat/completions`.
2. **Primary OpenRouter cost source:** `usage.cost` from the response or final SSE event.
3. **Cost fallback:** generation ID plus `total_cost` from `/api/v1/generation`.
4. **Capability constraints:** pair required capabilities such as tool calling and structured outputs with `provider.require_parameters: true`.
5. **Compatibility path:** retain Anthropic Messages as a separate transport; it no longer represents core's internal message model.
6. **Peer candidate:** do not make Responses API the default transport yet; add an adapter when nano needs richer item/event semantics, web search, or Responses SDK compatibility.
7. **Storage boundary:** wire responses are Source Records; Native Events, Journal Entries, and the Event Journal remain nano's own runtime-fact layer.
8. **Export boundary:** continue projecting ATIF from the Event Journal rather than constructing it directly from any provider response.

## 9. Validation scope of this research

The protocol conclusions come from OpenRouter's official API reference, feature guides, and usage-accounting documentation as of 2026-08-23, combined with static integration analysis of the current nano code. This research did not make an online request that would incur OpenRouter charges, so the example IDs, token counts, and amounts are illustrative rather than actual billing records from this project's account.

That limitation does not affect the protocol fields or architecture decision, but the implementation should add an opt-in live integration test using the least expensive available model to verify, for the current account:

- non-streaming `usage.cost`;
- the terminal usage event from streaming;
- reconciliation between `X-Generation-Id` and the Generation API;
- tool-call delta assembly;
- consistency among the response model, provider, and cost after fallback.
