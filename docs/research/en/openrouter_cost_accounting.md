# OpenRouter Actual Cost, Pricing APIs, and Trajectory Accounting

> Generated from the Chinese source [`../zh-CN/openrouter_cost_accounting.md`](../zh-CN/openrouter_cost_accounting.md). Do not edit by hand.

Surveyed on 2026-08-23.

## Question

> I use OpenRouter. Does the response contain the actual cost? If not, is there an API for retrieving model prices?
>
> Can cost accounting be implemented together with the native storage format or trajectory?

## Related research

For the protocol shape, agent capabilities, endpoint choice, and nano integration boundary of OpenRouter's model-independent API, see [OpenRouter's Unified Model Protocol: Capabilities, Cost, and the nanoPyCodeAgent Integration Boundary](openrouter_unified_protocol.md). This document focuses only on cost sources, delayed reconciliation, and trajectory mapping.

## Conclusions first

OpenRouter **does provide actual billed cost**, and it is more reliable than an estimate based on “tokens × the model's current list price.” The unified OpenRouter Chat Completions API returns `usage.cost` in the complete response or the final SSE event. nanoPyCodeAgent currently uses the Anthropic Messages compatibility endpoint, however, and that endpoint's Anthropic-shaped `usage` object does not publicly promise a `cost` field. As a result, `stream.get_final_message().usage` will usually expose only tokens.

The most reliable implementation for nano has two paths:

1. When a future Chat Completions transport is in use, write `usage.cost` directly to the `model.completed` Native Event as resolved, `provider_reported` cost.
2. When the current Anthropic Messages transport does not return cost directly, capture `X-Generation-Id` from the HTTP headers and initially mark cost as pending.
3. Call `GET /api/v1/generation?id=...` to retrieve that request's `total_cost`, then append a `model.cost_resolved` Native Event.
4. In both paths, let the journal writer persist the event as a Journal Entry and project it into ATIF `step.metrics.cost_usd`.
5. Preserve the generation ID for every OpenRouter request so missing cost can be reconciled and existing cost audited.
6. Treat the price catalog from `GET /api/v1/model/:author/:slug` or `GET /api/v1/models` only as a budgeting and estimation fallback, never as the historical bill of record.

## 1. Why OpenRouter documents cost but nano does not see it in the response

OpenRouter's [Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting) documentation says that a complete Chat Completions/Responses response, or the final SSE chunk, includes:

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

Here:

- `usage.cost` is the total charged to the current OpenRouter account.
- `cost_details.upstream_inference_cost` is the upstream provider's inference cost.
- With streaming, usage arrives in the final SSE event; without streaming, it is part of the complete response.
- The old `usage: {include: true}` and `stream_options.include_usage` parameters are no longer required.

OpenRouter's [FAQ](https://openrouter.ai/docs/faq) says that credits use US dollars as their base currency and that both site and API pricing are denominated in dollars. For ordinary credits requests, provider-reported `usage.cost` or `data.total_cost` can therefore map to ATIF `cost_usd`. Internal events should still preserve `currency: "USD"` and the source explicitly rather than letting a target field name imply both currency and provenance.

The current nano code in [`src/nanopycodeagent/agent.py`](../../../src/nanopycodeagent/agent.py) uses:

```text
anthropic.Anthropic
  -> ANTHROPIC_BASE_URL
  -> OpenRouter /api/v1/messages
  -> client.messages.stream(...)
  -> stream.get_final_message()
```

OpenRouter's [Anthropic Messages endpoint](https://openrouter.ai/docs/api/api-reference/anthropic-messages/create-messages) returns Anthropic-compatible `usage.input_tokens`, `usage.output_tokens`, and cache fields. Its public response schema does not list `usage.cost`. The `usage.cost` guarantee from Chat Completions therefore cannot be applied directly to the Messages skin.

The base models in the Anthropic Python SDK installed by this repository permit extra fields. If the server actually includes `cost` under `usage`, the SDK will not necessarily discard it. The problem is that OpenRouter's public Messages protocol does not promise to send the field, so an implementation cannot depend on that undeclared extension.

### 1.1 Evidence from four local CLI runs

On the same day, tests using a non-sensitive sentinel file ran Pi 0.84.2, Codex 0.149.0, Claude Code 2.1.237, and OpenCode 1.18.21 and observed:

| CLI | Cost in its output | Source assessment |
|---|---|---|
| Pi | Every assistant response has `usage.cost.total` | The source explicitly calls `calculateCost(model, usage)` using model-catalog rates |
| Codex | No cost in `exec --json` | Only turn-aggregate tokens |
| Claude Code | Terminal `result.total_cost_usd` and `modelUsage.*.costUSD` | Agent-reported aggregate; Anthropic Messages usage itself has no cost, and the result may include auxiliary model calls |
| OpenCode | Each `step_finish.cost`; the observed value was `0` | The source calculates from model-catalog prices and tokens; `0` does not necessarily prove the provider charged nothing |

This shows that “the agent emitted a cost number” and “the provider returned the actual bill” are different claims. A trajectory should distinguish at least:

- `provider_reported`: for example, OpenRouter generation `total_cost`.
- `agent_calculated`: for example, Pi or OpenCode calculating from a price catalog.
- `agent_reported`: for example, a Claude Code terminal result whose calculation details are encapsulated by the agent.
- `unknown`: for example, Codex's public JSONL, which provides no cost.

Only `provider_reported` directly answers “what did OpenRouter actually charge for this request?” The other values remain useful observations, but they must not be mixed into one unattributed total.

## 2. The Messages compatibility path and audit fallback: Generation API

OpenRouter creates a generation record for every request. Its official [Get a Generation](https://openrouter.ai/docs/api/api-reference/generations/get-generation) API is:

```http
GET https://openrouter.ai/api/v1/generation?id=gen-1234567890
Authorization: Bearer <OPENROUTER_API_KEY>
```

The important response fields are:

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

When the response body does not contain `usage.cost`, the trajectory should use `data.total_cost`, which represents the cost recorded against the OpenRouter account for that generation. If Chat Completions already returned `usage.cost`, the Generation API instead serves reconciliation and audit. `upstream_inference_cost` should not replace the amount actually charged to the account. The Usage Accounting documentation explicitly notes that, when looking up a Generation ID, this field is available only for BYOK requests; for non-BYOK requests it is normally `0` or `null`.

### 2.1 Where the generation ID comes from

Do not blindly reuse the Anthropic `message.id`. A Messages API message ID may be `msg_...`, while an OpenRouter generation ID is `gen-...`. OpenRouter supplies `X-Generation-Id` in the HTTP response headers.

The current Anthropic SDK stream object exposes the underlying response headers, so the existing `with client.messages.stream(...) as stream:` block can read:

```python
generation_id = stream.response.headers.get("x-generation-id")
```

After the response completes, save this value alongside `message.id`, model, and usage. If the header is missing, cost status should be unknown—not a synthetic zero.

### 2.2 Why this is more reliable than price-catalog arithmetic

The generation record already knows the final:

- model and provider;
- fallback and routing result;
- native-tokenizer input, output, cache, and reasoning tokens;
- billing rules in effect at the time;
- `total_cost` actually recorded against the OpenRouter account.

A price-catalog estimate is vulnerable to provider routing, fallback, cache reads and writes, reasoning, images, search, per-request charges, service tiers, and price changes. For the historical question “what did this run actually cost?”, the generation record is the more appropriate source of truth.

## 3. A model pricing API does exist, but it should be treated as an estimation tool

OpenRouter provides:

```http
GET https://openrouter.ai/api/v1/model/anthropic/claude-sonnet-4
GET https://openrouter.ai/api/v1/models
Authorization: Bearer <OPENROUTER_API_KEY>
```

The official [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models) returns data such as:

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

These string prices are dollar amounts per token, per request, or per corresponding unit. For example, `prompt = 0.00003` means `$30 / 1M tokens`. The website often displays prices per million tokens; do not divide the API value by another million.

The simplest text-only estimate is:

```text
estimated_cost =
    prompt_tokens     × pricing.prompt
  + completion_tokens × pricing.completion
  + request_count      × pricing.request
```

A real implementation must also handle any present `input_cache_read`, `input_cache_write`, `internal_reasoning`, image, web-search, and other billing fields, and must use `Decimal` rather than binary floating point for accounting.

The pricing API is appropriate for:

- pre-request budgeting and max-cost guards;
- showing approximate unit prices in a UI;
- clearly labeled estimates when a provider has no actual-cost API;
- offline model-price comparisons.

The pricing API is not appropriate for:

- backfilling OpenRouter's historical actual bill;
- guessing the final provider after automatic routing;
- applying current prices to past runs;
- presenting an estimate as reported cost when fields are missing.

## 4. Implementing this with Native Events, the Event Journal, and ATIF

### 4.1 Native Events express facts; Journal Entries are persisted immediately

If a Chat Completions response or terminal SSE event directly returns `usage.cost`, `model.completed` can immediately record:

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

This case does not require another Generation API query solely to obtain cost, though the generation ID should still be retained for audit.

If the current Anthropic Messages response has no cost, core first emits a `model.completed` Native Event when the model response completes. The journal writer adds persistence metadata and immediately appends the following Journal Entry without waiting for the cost lookup:

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

After the Generation API succeeds, append:

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

This has three benefits: model output is not lost when the cost API is temporarily unavailable; the append-only Event Journal never has to rewrite an old Journal Entry; and the ATIF projector can join the two Journal Entry payloads on `generation_id`.

### 4.2 ATIF mapping rules

When the generation lookup for a model call succeeds:

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

Populate run-level `final_metrics.total_cost_usd` with a sum only when every billable model call has resolved. If any generation is missing or its query fails:

- Known steps may still contain their own `metrics.cost_usd`.
- Do not fill an unknown step with `0`.
- Prefer omitting `final_metrics.total_cost_usd`.
- Record `known_cost_usd`, `cost_is_partial: true`, and the missing generation IDs under `final_metrics.extra`.

Zero is valid only when OpenRouter explicitly reports zero cost for the request, such as a genuinely free request or certain cache hits. It must never mean “no data was available.”

### 4.3 Query timing

The recommended sequence is:

1. Persist `model.completed` immediately when the model finishes.
2. If the response contains `usage.cost`, mark it resolved directly.
3. If cost is absent, query actual cost by generation ID during run finalization.
4. Use bounded retries because generation metadata becomes queryable asynchronously.
5. A failed query must not change the agent task's success or failure state; it only marks cost completeness as partial.
6. Finally, write the complete ATIF snapshot atomically.

If the CLI later needs to return as quickly as possible, cost enrichment can also happen offline. The Event Journal already contains the generation ID, so the ability to reconcile the bill is preserved.

## 5. Effect on the 0.8.x trajectory decision

Cost can ship in the same development series as trajectory, but it should be a provider-aware enrichment rather than OpenRouter HTTP logic embedded in the ATIF serializer:

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

This also shows why Native Events plus an Event Journal are more robust than assembling ATIF JSON directly during execution: actual cost may arrive after the model response, ATIF is a completed-state document, and the Event Journal naturally represents pending → resolved.

## Final answer

When you use OpenRouter, actual cost is available. The unified OpenRouter Chat Completions API can return `usage.cost` directly, and OpenRouter also exposes generation-specific `total_cost`. nano does not currently see those values mainly because it uses the Anthropic Messages compatibility protocol, whose `usage` schema does not promise to carry cost. See the [OpenRouter unified protocol survey](openrouter_unified_protocol.md) for the protocol choice and migration rationale.

In a future Chat Completions transport, prefer `usage.cost`. For the current Messages transport—or cases such as a stream ending before final usage—capture `X-Generation-Id` and call `/api/v1/generation` to backfill `total_cost`. Both values enter Native Events as provider-reported cost, are persisted by the journal writer as Journal Entries, and are eventually projected to ATIF. A model pricing API also exists, but it is better suited to budgeting and fallback estimation; it must not overwrite actual OpenRouter billing or present a current-price estimate as a historical bill.
