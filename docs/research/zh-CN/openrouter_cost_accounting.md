# OpenRouter 的真实 Cost、价格 API 与 Trajectory 记账方案

> 本文件为**中文源文件**（source of truth）；英文版 [`../en/openrouter_cost_accounting.md`](../en/openrouter_cost_accounting.md) 由其生成。

调研时间：2026-08-23。

## 问题

> 关于 cost，我用的是 OpenRouter，响应里没有真实 cost 吗？如果没有真实 cost，有 API 获取模型价格吗？
>
> cost 能和原生存储格式或 trajectory 一起实现吗？

## 相关调研

OpenRouter 模型无关 API 的协议形状、agent 能力、endpoint 选型和 nano 接入边界，见 [OpenRouter 统一模型协议：能力、Cost 与 nanoPyCodeAgent 接入边界](openrouter_unified_protocol.md)。本文只展开 cost 的来源、补账和 trajectory 映射。

## 结论先行

OpenRouter **有真实扣费数据**，而且比“token × 当前模型标价”的估算更可靠。OpenRouter Chat Completions 统一 API 会在完整 response 或最后一个 SSE event 中直接返回 `usage.cost`；但 nanoPyCodeAgent 当前走的是 Anthropic Messages 兼容端点，这个端点的 Anthropic 形状 `usage` 没有公开承诺 `cost` 字段，所以 `stream.get_final_message().usage` 通常只能看到 tokens。

对 nano 最可靠的实现分为两条路径：

1. 后续使用 Chat Completions transport 时，直接把 `usage.cost` 作为 resolved、`provider_reported` cost 写入 `model.completed` Native Event；
2. 当前 Anthropic Messages transport 没有直接 cost 时，从 HTTP header 捕获 `X-Generation-Id`，先把 cost 标为 pending；
3. 调用 `GET /api/v1/generation?id=...` 获取该次请求的 `total_cost`，再追加 `model.cost_resolved` Native Event；
4. 两条路径都由 journal writer 持久化为 Journal Entry，再投影到 ATIF `step.metrics.cost_usd`；
5. 所有 OpenRouter 请求都保留 generation ID，供缺失补账和对账；
6. `GET /api/v1/model/:author/:slug` 或 `GET /api/v1/models` 的价格表只作为预算/估算 fallback，不作为历史实际账单。

## 一、为什么 OpenRouter 文档说有 cost，nano 响应里却没有

OpenRouter 的 [Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting) 文档说明，Chat Completions/Responses 的完整响应或最后一个 SSE chunk 会带：

```json
{
  "usage": {
    "prompt_tokens": 194,
    "completion_tokens": 2,
    "total_tokens": 196,
    "cost": 0.00095,
    "cost_details": {
      "upstream_inference_cost": 0.00090
    }
  }
}
```

其中：

- `usage.cost` 是向当前 OpenRouter 账户收取的总额；
- `cost_details.upstream_inference_cost` 是上游 provider 推理成本；
- streaming 时 usage 在最后一个 SSE event，非 streaming 时在完整响应；
- 不再需要旧的 `usage: {include: true}` 或 `stream_options.include_usage` 参数。

OpenRouter [FAQ](https://openrouter.ai/docs/faq) 说明 credits 的基础货币是美元，站点和 API 定价也以美元表示；因此普通 credits 请求可以把 provider-reported `usage.cost` 或 `data.total_cost` 映射为 ATIF `cost_usd`。内部事件仍应显式保存 `currency: "USD"` 与 source，不能仅靠目标字段名隐含币种和来源。

但 nano 当前代码在 [`src/nanopycodeagent/agent.py`](../../../src/nanopycodeagent/agent.py) 中使用：

```text
anthropic.Anthropic
  -> ANTHROPIC_BASE_URL
  -> OpenRouter /api/v1/messages
  -> client.messages.stream(...)
  -> stream.get_final_message()
```

OpenRouter 的 [Anthropic Messages endpoint](https://openrouter.ai/docs/api/api-reference/anthropic-messages/create-messages) 返回 Anthropic 兼容的 `usage.input_tokens`、`usage.output_tokens` 和 cache 字段；该端点的公开 response schema 没有列 `usage.cost`。因此不能把 Chat Completions 的 `usage.cost` 承诺直接套到 Messages skin 上。

仓库当前安装的 Anthropic Python SDK 基础模型允许额外字段：如果服务器真的在 `usage` 中附加 `cost`，SDK 不会必然删除它；问题是 OpenRouter Messages 的公开协议没有承诺发送该字段。实现不能依赖一个未声明扩展。

### 1.1 本机四个 CLI 的实测旁证

同日使用无敏感哨兵文件实测 Pi 0.84.2、Codex 0.149.0、Claude Code 2.1.237 和 OpenCode 1.18.21，观察到：

| CLI | 输出的 cost | 来源判断 |
|---|---|---|
| Pi | 每个 assistant response 都有 `usage.cost.total` | 源码明确由 `calculateCost(model, usage)` 用模型目录费率计算 |
| Codex | `exec --json` 无 cost | 只有 turn aggregate tokens |
| Claude Code | terminal `result.total_cost_usd` 与 `modelUsage.*.costUSD` | agent-reported 汇总；Anthropic Messages usage 本身没有 cost，且结果可含辅助模型调用 |
| OpenCode | 每个 `step_finish.cost`；本次实际为 `0` | 源码按模型价格表和 tokens 计算；`0` 未必能证明 provider 未扣费 |

这说明“agent 输出了一个 cost 数字”与“provider 返回了实际账单”是两件事。trajectory 最好明确区分：

- `provider_reported`：例如 OpenRouter generation `total_cost`；
- `agent_calculated`：例如 Pi/OpenCode 用价格目录计算；
- `agent_reported`：例如 Claude Code terminal result，计算细节由 agent 封装；
- `unknown`：例如 Codex 公开 JSONL 没有 cost。

只有 `provider_reported` 可以直接回答“OpenRouter 这次实际记账多少”。其他值仍有观测价值，但不能无来源地混入同一个 total。

## 二、Messages 兼容路径与审计 fallback：Generation API

OpenRouter 为每次请求建立 generation record。官方 [Get a Generation](https://openrouter.ai/docs/api/api-reference/generations/get-generation) API 是：

```http
GET https://openrouter.ai/api/v1/generation?id=gen-1234567890
Authorization: Bearer <OPENROUTER_API_KEY>
```

响应关键字段如下：

```json
{
  "data": {
    "id": "gen-1234567890",
    "model": "anthropic/claude-sonnet-4",
    "provider_name": "Anthropic",
    "streamed": true,
    "native_tokens_prompt": 120,
    "native_tokens_completion": 24,
    "native_tokens_cached": 0,
    "native_tokens_reasoning": 0,
    "total_cost": 0.00072,
    "usage": 0.00072,
    "upstream_inference_cost": null
  }
}
```

当 response body 没有 `usage.cost` 时，trajectory 应使用 `data.total_cost`：它表示这次 generation 实际记到 OpenRouter 账户的成本。若 Chat Completions 已直接返回 `usage.cost`，Generation API 则用于缺失补账和审计。`upstream_inference_cost` 不应替代账户实际扣费；Usage Accounting 文档明确说明，通过 Generation ID 查询时该字段只对 BYOK 请求可用，非 BYOK 通常为 `0` 或 `null`。

### 2.1 generation ID 从哪里拿

不能盲目使用 Anthropic `message.id`。Messages API 的消息 ID 可以是 `msg_...`，OpenRouter generation ID 则是 `gen-...`。OpenRouter 在 HTTP response header 中提供 `X-Generation-Id`。

当前 Anthropic SDK 的 stream 对象暴露底层 response headers，所以在现有 `with client.messages.stream(...) as stream:` 块内即可读取：

```python
generation_id = stream.response.headers.get("x-generation-id")
```

应在响应完成后将它与 `message.id`、model、usage 一起保存。若 header 缺失，cost 状态应是 unknown，而不是把 `0` 当作未知值。

### 2.2 为什么它比价格表计算可靠

Generation record 已经知道最终实际使用的：

- model 与 provider；
- fallback/routing 结果；
- native tokenizer 的输入、输出、cache 和 reasoning tokens；
- 当时生效的计费规则；
- OpenRouter 实际计入账户的 `total_cost`。

价格表估算则容易受 provider routing、fallback、cache read/write、reasoning、图片、搜索、按请求收费、service tier 和价格变更影响。对“这次历史运行到底花了多少”这个问题，generation record 是更合适的事实来源。

## 三、确实有模型价格 API，但应定位为估算工具

OpenRouter 提供：

```http
GET https://openrouter.ai/api/v1/model/anthropic/claude-sonnet-4
GET https://openrouter.ai/api/v1/models
Authorization: Bearer <OPENROUTER_API_KEY>
```

官方 [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models) 返回类似：

```json
{
  "data": {
    "id": "openai/gpt-4",
    "pricing": {
      "prompt": "0.00003",
      "completion": "0.00006",
      "request": "0",
      "image": "0"
    }
  }
}
```

API 中这些字符串价格是每 token/每 request/每相应单位的美元价格；例如 `prompt = 0.00003` 等于 `$30 / 1M tokens`。页面常以每百万 token 展示，不要再额外除一百万。

最简单的文本估算是：

```text
estimated_cost =
    prompt_tokens     × pricing.prompt
  + completion_tokens × pricing.completion
  + request_count      × pricing.request
```

实际实现还必须按存在的字段处理 `input_cache_read`、`input_cache_write`、`internal_reasoning`、image、web search 等计费项，并使用 `Decimal`，不要用二进制 float 做账。

价格 API 适合：

- 请求前预算和 max-cost guard；
- UI 展示大致单价；
- provider 没有实际 cost API 时的明确标注估算；
- 离线比较模型价格。

价格 API 不适合：

- 回填 OpenRouter 历史实际账单；
- 自动路由后猜最终 provider；
- 把当前价格套到过去运行；
- 在字段缺失时把估算冒充 reported cost。

## 四、怎样与 Native Event、Event Journal 和 ATIF 一起实现

### 4.1 Native Event 表达事实，Journal Entry 立即落盘

若 Chat Completions response 或 terminal SSE event 已直接返回 `usage.cost`，`model.completed` 可以立即记录：

```json
{
  "cost": {
    "status": "resolved",
    "amount": "0.00072",
    "currency": "USD",
    "source": "openrouter_response.usage.cost",
    "kind": "provider_reported"
  }
}
```

这种情况不需要仅为取得 cost 再查询一次 Generation API，但仍应保存 generation ID 以便审计。

若当前 Anthropic Messages response 没有 cost，模型响应完成时，core 先产生 `model.completed` Native Event；journal writer 添加持久化元数据并立即追加下面的 Journal Entry，不等待价格查询：

```json
{
  "schema_version": 1,
  "run_id": "run-123",
  "seq": 12,
  "recorded_at": "2026-08-23T08:00:01.250Z",
  "type": "model.completed",
  "payload": {
    "provider": "openrouter",
    "model": "anthropic/claude-sonnet-4",
    "message_id": "msg_abc123",
    "generation_id": "gen-1234567890",
    "usage": {
      "input_tokens": 120,
      "output_tokens": 24,
      "cache_read_input_tokens": 0,
      "cache_creation_input_tokens": 0
    },
    "cost": {
      "status": "pending",
      "source": "openrouter_generation"
    }
  }
}
```

Generation API 成功后再追加：

```json
{
  "schema_version": 1,
  "run_id": "run-123",
  "seq": 13,
  "recorded_at": "2026-08-23T08:00:01.520Z",
  "type": "model.cost_resolved",
  "payload": {
    "generation_id": "gen-1234567890",
    "amount": "0.00072",
    "currency": "USD",
    "source": "openrouter_generation.total_cost",
    "model": "anthropic/claude-sonnet-4",
    "provider_name": "Anthropic"
  }
}
```

这样做有三个好处：模型输出不会因为 cost API 暂时不可用而丢失；append-only Event Journal 不需要回头改旧 Journal Entry；ATIF projector 可以用 `generation_id` join 两条 Journal Entry 的 payload。

### 4.2 ATIF 的映射规则

若一次模型调用的 generation 查询成功：

```json
{
  "metrics": {
    "prompt_tokens": 120,
    "completion_tokens": 24,
    "cached_tokens": 0,
    "cost_usd": 0.00072,
    "extra": {
      "cost_source": "openrouter_generation.total_cost",
      "generation_id": "gen-1234567890"
    }
  }
}
```

run 级 `final_metrics.total_cost_usd` 只有在所有应计费 model call 都 resolved 时才填写为总和。若任何 generation 缺失或查询失败：

- 已知 step 仍可填写各自的 `metrics.cost_usd`；
- 不要把未知 step 填成 `0`；
- 建议省略 `final_metrics.total_cost_usd`；
- 在 `final_metrics.extra` 记录 `known_cost_usd`、`cost_is_partial: true` 和缺失 generation IDs。

`0` 只能表示 OpenRouter 明确报告此次 cost 为零，例如真正免费的请求或某些 cache hit；它不能表示“没拿到数据”。

### 4.3 查询时机

推荐流程是：

1. 模型完成立即落 `model.completed`；
2. response 已带 `usage.cost` 时直接标为 resolved；
3. cost 缺失时在 run 收尾阶段按 generation ID 查询真实 cost；
4. 使用有界 retry，因为 generation metadata 是异步可查的；
5. 查询失败不改变 agent 任务成功/失败状态，只把 cost completeness 标成 partial；
6. 最后原子写入完整 ATIF 快照。

若将来只需要尽快返回 CLI 结果，也可以让 cost enrichment 离线进行；Event Journal 中已有 generation ID，不会失去补账能力。

## 五、对 0.8.x trajectory 的决策影响

cost 可以和 trajectory 同一期实现，但应拆成 provider-aware enrichment，而不是把 OpenRouter HTTP 逻辑写进 ATIF serializer：

```text
OpenRouter Chat response ─ usage.cost ─────────────┐
                                                   ↓
Anthropic Messages response ─ generation_id ─ cost resolver
                                                   │
                                                   ↓
                              Native Event + Journal Entry
                                                   │
                                                   ↓
                                            Event Journal
                                                   │
                                                   ↓
                                            ATIF projector
```

这也说明为什么 Native Event + Event Journal 比“直接边跑边拼 ATIF JSON”更稳：实际 cost 可能晚于模型响应到达，ATIF 是完成态文档，而 Event Journal 能自然表达 pending → resolved。

## 最终回答

你用 OpenRouter 时，真实 cost 并不是算不出来。OpenRouter Chat Completions 统一 API 可以直接返回 `usage.cost`，OpenRouter 也有准确到 generation 的 `total_cost`。nano 当前看不到，主要因为它使用 Anthropic Messages 兼容协议，而该协议的 `usage` schema 没有承诺直接携带 cost。协议选型与迁移依据见 [OpenRouter 统一模型协议调研](openrouter_unified_protocol.md)。

实现上，后续 Chat Completions transport 应优先读取 `usage.cost`；当前 Messages transport 或提前断流等缺失场景则捕获 `X-Generation-Id`，调用 `/api/v1/generation` 回填 `total_cost`。两者都作为 provider-reported cost 进入 Native Event，再由 journal writer 持久化为 Journal Entry，最终投影到 ATIF。模型价格 API 也存在，但它更适合预算和 fallback estimation，不应覆盖 OpenRouter 返回的真实扣费，也不应把当前价格估算冒充历史账单。
