# How Source Records, Internal Events, and ATIF Correspond Across Pi, Claude Code, Codex, OpenCode, and Grok

> Generated from the Chinese source [`../zh-CN/agent_events_to_atif_examples.md`](../zh-CN/agent_events_to_atif_examples.md). Do not edit by hand.

Surveyed on 2026-08-23.

## Question

> Can you show realistic examples of what agent-internal events look like in Pi, Codex, Claude Code, OpenCode, and Grok, and what the corresponding ATIF looks like?
>
> Why do these native-event examples have no timestamps?

## Conclusions first

Yes, but both “real” and “internal” need precise boundaries. This document uses two evidence layers. The earlier “Local runtime evidence” section preserves IDs, token counts, and timestamps from four actual Pi, Codex, Claude Code, and OpenCode stdout runs. Those records are **Source Records** visible at CLI or SDK boundaries and must not all be treated as raw events from an agent core. The five later comparative examples are **schema-faithful reconstructions** based on real type definitions, converters, and tests; their task content, IDs, token counts, and timestamps are illustrative values chosen for comparison. Grok was not installed locally, so it has only a source-based reconstruction.

All five projects follow the same broad pattern: **the agent loop first produces its own messages, events, or state; a CLI or SDK projects them into Source Records; ATIF is an evaluation view assembled afterward, not the object model in which the loop itself runs.** The main differences are:

1. Whether Source Records are organized around model messages, tool states, or CLI items.
2. Whether token and cost data is available for every model call or only aggregated at the end of a run or turn.
3. Whether source time is present on the Source Record, nested in its payload, or available only as receiver-captured time.

## Concepts and conversion relationships

This document uses the terminology in the repository-root [`CONTEXT.md`](../../../CONTEXT.md):

| Concept | Definition | Must not be conflated with |
|---|---|---|
| **Source Record** | An agent-specific record that an adapter actually observes at a third-party CLI, SDK, or protocol boundary; it may already be a reduced projection of internal state | nano Native Event, Journal Entry |
| **Native Event** | An agent-independent runtime fact produced directly by nano core or normalized by an adapter from a Source Record | A raw third-party stdout line, ATIF step |
| **Journal Entry** | A Native Event plus identity, ordering, and recording-time metadata required for persistence | A separate “persistence envelope” artifact, trajectory step |
| **Event Journal** | The internal fact log formed by one Agent Run's Journal Entries in append order | Public Event Stream, Trajectory, Session |
| **ATIF Trajectory** | The public completed evaluation and analysis view projected from the Event Journal | Event Journal, native JSONL |

For a third-party agent, the complete boundary is:

```text
Third-party internal state/events
        ↓ third-party CLI/SDK projector
Source Record
        ↓ nano adapter normalization
Native Event
        ↓ journal writer adds run_id / seq / recorded_at
Journal Entry
        ↓ append-only persistence (JSONL is one possible encoding)
Event Journal
        ↓ ATIF projector
ATIF Trajectory
```

nano's own core can produce Native Events directly, skipping the first two steps. JSONL here is only a physical encoding with one Journal Entry per line, and append-only is only the write policy; neither defines a new trajectory semantic model. The earlier phrase “persistence envelope” is likewise not a separate domain concept and is standardized here as **Journal Entry**.

The observed stdout maps to these concepts as follows:

| Agent | Source Record captured here | Distance from internal events | Journal Entry? |
|---|---|---|---|
| Pi | Session, message, and tool lines from `--mode json` | Most event lines are direct public serializations of `AgentEvent`; the session header is a CLI protocol record | No; a separate, unshown persistent harness entry is closer to a Journal Entry |
| Claude Code | System, assistant, user, and result messages from SDK `stream-json` | Already a public SDK protocol; it cannot be assumed identical to the internal event bus | No; session persistence was also disabled for this run |
| Codex | `ThreadEvent` from `exec --json` | A reduced projection of a lower-level protocol | No; the local rollout JSONL is another persistence artifact and is not the stdout source used here |
| OpenCode | Step, tool, and text lines from `run --format json` | Projected again from internal `message.part.updated` events | No; the CLI's top-level timestamp is not journal ordering metadata |
| Grok | `AcpLine` from `streaming-json` | Reduced from ACP updates | No; it has NDJSON line order but no Journal Entry envelope |

Timestamps in simplified examples must not be used to infer the source protocol. The actual situation is:

| Agent | Uniform time on Source Records | Other available time | Recommended ATIF time source |
|---|---|---|---|
| Pi | `AgentEvent` has none | The session header and `AgentMessage.timestamp` have time; a persistent harness entry has a separate storage timestamp | Prefer message time; let the collector add receive time for tool events |
| Claude Code | No uniform time on the SDK stream | In local 2.1.237, `assistant` and `user` messages have ISO timestamps; `system` and `result` do not, while `result` has duration | Use message time when available, otherwise receive time |
| Codex `exec --json` | `ThreadEvent` has none | Some lower-level protocol objects have start/end times, but public `ThreadEvent` omits them | Add receive time in the JSONL receiver |
| OpenCode | Yes | `message.part.updated.properties.time`; message and tool state also have create/start/end time | Use native millisecond time directly |
| Grok `streaming-json` | None | The terminal event has usage; the internal persistence layer has other sequencing data, but the public reducer omits it | Add receive time in the JSONL receiver |

nanoPyCodeAgent Journal Entries should therefore not reproduce gaps in any one public stream. Every Journal Entry should have at least a strictly increasing `seq` and UTC `recorded_at`: the former is authoritative ordering within a run, and the latter is when nano accepted or recorded the fact. If a Source Record contains reliable time, preserve it on the Native Event as `source_timestamp`. Wall clocks can move backward or assign identical times to concurrent events, so neither kind of timestamp can be the only ordering mechanism.

## Research scope

This document uses fixed snapshots under the repository's `references/` directory:

- Pi: `c49906ec77788625aacbdc53ebca6fbe65bd20f5`
- Codex: `4f39251a010a8bd7d692d25fb33832ff06f1635a`
- Unofficial Claude Code source snapshot: `a371abbe75ffa0d0a3c92290e2bbf56a7ef54367`
- OpenCode: `e00890c67261a435cee6409366a68999a93393fd`
- Grok Build: `19d42e35c07a9c9244f03f6df0c4c353f970d4f9`
- Harbor: 0.21.0 as pinned by [`benchmarks/harbor/pyproject.toml`](../../../benchmarks/harbor/pyproject.toml), whose trajectory schema is ATIF-v1.7

### Local runtime evidence

In addition to source research, this document records actual runs of four locally installed CLIs on 2026-08-23:

| CLI | Version | Result |
|---|---:|---|
| Pi | 0.84.2 | Success; `openai-codex/gpt-5.6-sol`, two model responses, and one `read` |
| Codex | 0.149.0 | Success; two command-item states and one agent message |
| Claude Code | 2.1.237 | Success; two Claude Opus messages, one `Read`, plus auxiliary Haiku usage |
| OpenCode | 1.18.21 | Success; two steps and one `read` |

To avoid sending repository contents to external models, all four tests ran in a temporary directory under `/tmp` and read only a purpose-built, non-sensitive file. The following preparation creates a new random directory; `$probe_dir` in later commands refers to it:

```bash
probe_dir="$(mktemp -d /tmp/nanopy-agent-event-probe.XXXXXX)"
printf 'NANOPY_EVENT_PROBE_20260823\n' > "$probe_dir/probe.txt"
cd "$probe_dir"
```

The successful captures used these commands. A rerun will naturally produce new session and message IDs, token counts, and timestamps.

Pi:

```bash
pi --mode json --print --no-session \
  --tools read \
  --no-extensions \
  --no-skills \
  --no-prompt-templates \
  --no-themes \
  --no-context-files \
  --approve \
  "Use the read tool exactly once to read probe.txt. Do not write or modify anything. Then reply with only the exact file content."
```

Codex:

```bash
codex exec --json \
  --sandbox read-only \
  --ephemeral \
  --skip-git-repo-check \
  --ignore-user-config \
  "Read probe.txt using a shell command exactly once. Do not write or modify anything. Then reply with only the exact file content."
```

Claude Code:

```bash
claude -p \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --safe-mode \
  --tools Read \
  --permission-mode dontAsk \
  "Use the Read tool exactly once to read probe.txt. Do not write or modify anything. Then reply with only the exact file content."
```

OpenCode; its local installation path is added by `.zshrc`, so the observed procedure loads it first:

```bash
source ~/.zshrc
opencode run \
  --format json \
  --pure \
  --auto \
  --dir "$probe_dir" \
  "Use the read tool exactly once to read probe.txt. Do not write or modify anything. Then reply with only the exact file content."
```

The following records extract the relevant parts of actual stdout. Each excerpt selects only events or fields needed for structural comparison: complete Pi and Claude Code lines contain large encrypted-reasoning, initialization, and plugin-list fields, while OpenCode tool output and metadata are also reduced. Event names, IDs, numeric values, and times all come from the actual runs. These are **key-field projections of real stdout**, not untouched line-by-line captures.

#### Pi 0.84.2

```jsonl
{"type":"session","version":3,"id":"01a02e3c-e606-7060-baf2-9a1ded866776","timestamp":"2026-08-23T10:48:58.118Z","cwd":"/tmp/nanopy-agent-event-probe.ktOr9V"}
{"type":"message_end","message":{"role":"assistant","model":"gpt-5.6-sol","provider":"openai-codex","responseId":"resp_0f6a0eea8b7401c0016a8ad01c304087d0a882c3eee1686e09","usage":{"input":597,"output":30,"reasoning":10,"totalTokens":627,"cost":{"total":0.0038850000000000004}},"stopReason":"toolUse","timestamp":1787482138161}}
{"type":"tool_execution_start","toolCallId":"call_j2gAtuUWhalLvXqYLKLke6Yk|fc_0f6a0eea8b7401c0016a8ad01e705c87d0a0c8b9b64c05762e","toolName":"read","args":{"path":"probe.txt"}}
{"type":"tool_execution_end","toolCallId":"call_j2gAtuUWhalLvXqYLKLke6Yk|fc_0f6a0eea8b7401c0016a8ad01e705c87d0a0c8b9b64c05762e","toolName":"read","result":{"content":[{"type":"text","text":"NANOPY_EVENT_PROBE_20260823\n"}]},"isError":false}
{"type":"message_end","message":{"role":"assistant","model":"gpt-5.6-sol","provider":"openai-codex","responseId":"resp_0f6a0eea8b7401c0016a8ad01f3c5c87d0910ad017f42f5588","content":[{"type":"text","text":"NANOPY_EVENT_PROBE_20260823"}],"usage":{"input":648,"output":14,"reasoning":0,"totalTokens":662,"cost":{"total":0.00366}},"stopReason":"stop","timestamp":1787482143410}}
```

This directly verifies that tool-lifecycle events have no timestamp, while assistant and tool-result payloads do; per-response usage is rich. Pi's source [`calculateCost`](../../../references/pi/packages/ai/src/models.ts) multiplies tokens by model-catalog rates, so `usage.cost` is agent-calculated and must not automatically be treated as a provider charge.

#### Codex 0.149.0

```jsonl
{"type":"thread.started","thread_id":"01a02e3d-3743-7ac1-8c30-6c7254135573"}
{"type":"turn.started"}
{"type":"item.started","item":{"id":"item_0","type":"command_execution","command":"/usr/bin/zsh -lc 'cat probe.txt'","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_0","type":"command_execution","command":"/usr/bin/zsh -lc 'cat probe.txt'","aggregated_output":"NANOPY_EVENT_PROBE_20260823\n","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"NANOPY_EVENT_PROBE_20260823"}}
{"type":"turn.completed","usage":{"input_tokens":31003,"cached_input_tokens":19968,"cache_write_input_tokens":0,"output_tokens":135,"reasoning_output_tokens":60}}
```

This output confirms two gaps completely: it has no timestamps and no cost, while usage appears only as a `turn.completed` aggregate.

#### Claude Code 2.1.237

```jsonl
{"type":"system","subtype":"api_retry","attempt":1,"max_retries":10,"retry_delay_ms":524,"error_status":401,"error":"authentication_failed","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"assistant","message":{"model":"claude-opus-5","id":"msg_011CeKYuCnCMFvi24JSsJLvS","content":[{"type":"tool_use","id":"toolu_01BdirHMfK8eKMQgjDn2z7KA","name":"Read","input":{"file_path":"/tmp/nanopy-agent-event-probe.ktOr9V/probe.txt"}}],"usage":{"input_tokens":2,"cache_creation_input_tokens":2521,"cache_read_input_tokens":1247,"output_tokens":14}},"timestamp":"2026-08-23T10:50:01.254Z","request_id":"req_011CeKYuC24Db1xnVkk2y6Ai","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01BdirHMfK8eKMQgjDn2z7KA","type":"tool_result","content":"1\tNANOPY_EVENT_PROBE_20260823\n2\t"}]},"timestamp":"2026-08-23T10:50:01.307Z","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"assistant","message":{"model":"claude-opus-5","id":"msg_011CeKYuMzLUNjC8x7bv2GJD","content":[{"type":"text","text":"NANOPY_EVENT_PROBE_20260823"}],"usage":{"input_tokens":2,"cache_creation_input_tokens":130,"cache_read_input_tokens":3768,"output_tokens":1}},"timestamp":"2026-08-23T10:50:02.486Z","request_id":"req_011CeKYuMBxrDUiGKVmhMFzJ","session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
{"type":"result","subtype":"success","num_turns":2,"total_cost_usd":0.032467499999999996,"modelUsage":{"claude-haiku-4-5-20251001":{"inputTokens":920,"outputTokens":12,"costUSD":0.00098},"claude-opus-5[1m]":{"inputTokens":4,"outputTokens":98,"cacheReadInputTokens":5015,"cacheCreationInputTokens":2651,"costUSD":0.031487499999999995}},"result":"NANOPY_EVENT_PROBE_20260823","duration_ms":7920,"session_id":"9408bea7-c831-4edd-9a00-e7475e63fb4b"}
```

This corrects a difference between the fixed source snapshot and the newer local version: assistant and user messages in 2.1.237 now carry timestamps and request IDs, but `system.api_retry` and `result` still have no uniform timestamp. `result.total_cost_usd` also includes a Haiku auxiliary call beyond the visible Opus turns, so run total cannot be reconstructed by summing only visible assistant messages.

#### OpenCode 1.18.21

```jsonl
{"type":"step_start","timestamp":1787482258116,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"messageID":"msg_02e3eaf250017z8BF8zCT2CQ3f","type":"step-start"}}
{"type":"tool_use","timestamp":1787482259124,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"type":"tool","tool":"read","callID":"call_Kap3tANM5Uu9U5raX0ogDuYu","state":{"status":"completed","input":{"filePath":"/tmp/nanopy-agent-event-probe.ktOr9V/probe.txt"},"output":"NANOPY_EVENT_PROBE_20260823","time":{"start":1787482259101,"end":1787482259121}},"messageID":"msg_02e3eaf250017z8BF8zCT2CQ3f"}}
{"type":"step_finish","timestamp":1787482259168,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"reason":"tool-calls","messageID":"msg_02e3eaf250017z8BF8zCT2CQ3f","type":"step-finish","tokens":{"total":8011,"input":7952,"output":35,"reasoning":24,"cache":{"write":0,"read":0}},"cost":0}}
{"type":"step_start","timestamp":1787482261701,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"messageID":"msg_02e3ebedc001joGNk0E3u0NSp7","type":"step-start"}}
{"type":"text","timestamp":1787482261701,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"messageID":"msg_02e3ebedc001joGNk0E3u0NSp7","type":"text","text":"NANOPY_EVENT_PROBE_20260823","time":{"start":1787482261684,"end":1787482261691}}}
{"type":"step_finish","timestamp":1787482261701,"sessionID":"ses_fd1c15233ffeiwqf92JsdPfahU","part":{"reason":"stop","messageID":"msg_02e3ebedc001joGNk0E3u0NSp7","type":"step-finish","tokens":{"total":8113,"input":397,"output":16,"reasoning":20,"cache":{"write":0,"read":7680}},"cost":0}}
```

The OpenCode CLI does not print the internal SDK `message.part.updated` unchanged. [`run.ts`](../../../references/opencode/packages/opencode/src/cli/cmd/run.ts) projects it into the `step_start/tool_use/step_finish/text` records above and adds a top-level timestamp to every line with `Date.now()`. The observed `cost: 0` is only the agent-reported value OpenCode produced for the configured model; without a provider billing source, it cannot prove that the call was actually free.

### Projecting the observed events into ATIF

The four observed runs use these mapping strategies:

| CLI | ATIF step boundary | Timestamp | Step metrics | Run cost |
|---|---|---|---|---|
| Pi | Every completed assistant message | Message Unix milliseconds | Per-response tokens; locally calculated cost goes under `metrics.extra.estimated_cost_usd` | Not treated as actual `total_cost_usd` |
| Codex | Command-item step plus final-message step | Receiver-added | Turn aggregate belongs only in `final_metrics` | Missing |
| Claude Code | Every assistant `message.id` | Assistant timestamp | Visible message usage; prompt tokens must sum input + cache create + cache read | `result.total_cost_usd` can be an agent-reported run cost, annotated as including auxiliary calls |
| OpenCode | Every `messageID`, closed by `step_finish` | CLI top-level timestamp | Per-step tokens; cache is a prompt subset | Mark cost agent-reported; do not present it as provider-reported |

For the observed Claude Code run, the key ATIF fields cannot simply copy `input_tokens`. ATIF defines `prompt_tokens` to include both cached and non-cached tokens, so the first visible Opus step is `2 + 2521 + 1247 = 3770`, and the second is `2 + 130 + 3768 = 3900`:

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

Here `final_metrics` aggregates Opus and auxiliary Haiku from `modelUsage`, so it exceeds the sum of the two visible steps. That discrepancy must remain documented; hidden calls must not be discarded or Haiku tokens forced onto a visible step merely to make the totals equal.

For easier comparison, all five reconstructed examples use the same task:

```text
Read src/main.rs, then summarize what it does.
```

The following ATIF snippets expand only mapping-relevant fields under `steps`. A complete document also requires root fields such as `schema_version` and `agent`. ATIF-v1.7 defines `Step.timestamp` as an optional ISO 8601 string. nano should nevertheless populate it whenever a reliable source exists and record that source under `extra.timestamp_source`.

---

## 1. Pi: events around turns, messages, and tool execution

Pi's real `AgentEvent` union is defined in [`packages/agent/src/types.ts`](../../../references/pi/packages/agent/src/types.ts), with JSONL documented in [`packages/coding-agent/docs/json.md`](../../../references/pi/packages/coding-agent/docs/json.md). Event types include:

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

### 1.1 What Pi's public AgentEvent serialization looks like

The example omits text deltas and keeps only authoritative completion events for one tool call and two model responses:

```jsonl
{"type":"session","version":3,"id":"pi-session-1","timestamp":"2026-08-23T08:00:00.000Z","cwd":"/workspace"}
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"user","content":"Read src/main.rs, then summarize what it does.","timestamp":1787472000100}}
{"type":"message_end","message":{"role":"user","content":"Read src/main.rs, then summarize what it does.","timestamp":1787472000100}}
{"type":"tool_execution_start","toolCallId":"call_read_1","toolName":"read","args":{"path":"src/main.rs"}}
{"type":"tool_execution_end","toolCallId":"call_read_1","toolName":"read","result":{"content":"fn main() { println!(\"hello\"); }"},"isError":false}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"I will read the entry-point file first."},{"type":"toolCall","id":"call_read_1","name":"read","arguments":{"path":"src/main.rs"}}],"api":"anthropic-messages","provider":"anthropic","model":"claude-sonnet-4","usage":{"input":120,"output":24,"cacheRead":0,"cacheWrite":0,"totalTokens":144,"cost":{"input":0.00036,"output":0.00036,"cacheRead":0,"cacheWrite":0,"total":0.00072}},"stopReason":"toolUse","timestamp":1787472001250},"toolResults":[{"role":"toolResult","toolCallId":"call_read_1","toolName":"read","content":[{"type":"text","text":"fn main() { println!(\"hello\"); }"}],"isError":false,"timestamp":1787472001420}]}
{"type":"turn_start"}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"This is a minimal Rust program whose main function prints hello to standard output."}],"api":"anthropic-messages","provider":"anthropic","model":"claude-sonnet-4","usage":{"input":168,"output":31,"cacheRead":0,"cacheWrite":0,"totalTokens":199,"cost":{"input":0.000504,"output":0.000465,"cacheRead":0,"cacheWrite":0,"total":0.000969}},"stopReason":"stop","timestamp":1787472002100},"toolResults":[]}
```

The time semantics are mixed:

- The session header has an ISO timestamp.
- The `AgentEvent` envelopes for `turn_start` and `tool_execution_start/end` have no timestamp.
- The real `UserMessage`, `AssistantMessage`, and `ToolResultMessage` types have Unix-millisecond `timestamp` fields; see [`packages/ai/src/types.ts`](../../../references/pi/packages/ai/src/types.ts).
- Pi's newer persistent harness entries also have storage-assigned timestamps, but that is another journal layer, not the Source Records above.

### 1.2 Corresponding ATIF

```json
{
  "steps": [
    {
      "step_id": 1,
      "timestamp": "2026-08-23T08:00:00.100Z",
      "source": "user",
      "message": "Read src/main.rs, then summarize what it does.",
      "extra": {"timestamp_source": "user_message"}
    },
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.250Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "I will read the entry-point file first.",
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
      "message": "This is a minimal Rust program whose main function prints hello to standard output.",
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

Pi comes closest of the five to a lossless per-model-call mapping: `turn_end.message` already carries model, content, tool calls, usage, and timestamp, while `toolResults` preserves call association. Cost still needs provenance: mainstream provider adapters currently calculate it from model-catalog rates, so structural completeness does not make it a provider charge.

---

## 2. Claude Code: the SDK message stream must be joined by message ID and tool_use ID

Claude Code's SDK output types are defined in [`src/entrypoints/sdk/coreSchemas.ts`](../../../references/claude-code/src/entrypoints/sdk/coreSchemas.ts). Harbor's Claude Code adapter uses `--output-format=stream-json --print`, then organizes multiple SDK messages into ATIF.

### 2.1 What Claude Code SDK Source Records look like

```jsonl
{"type":"system","subtype":"init","cwd":"/workspace","tools":["Read"],"model":"claude-sonnet-4","permissionMode":"bypassPermissions","uuid":"sys-1","session_id":"claude-session-1","apiKeySource":"ANTHROPIC_API_KEY","mcp_servers":[],"slash_commands":[],"output_style":"default","skills":[],"plugins":[],"claude_code_version":"2.x"}
{"type":"assistant","message":{"id":"msg_tool_1","type":"message","role":"assistant","model":"claude-sonnet-4","content":[{"type":"text","text":"I will read the entry-point file first."},{"type":"tool_use","id":"toolu_read_1","name":"Read","input":{"file_path":"/workspace/src/main.rs"}}],"stop_reason":"tool_use","stop_sequence":null,"usage":{"input_tokens":120,"output_tokens":24,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"parent_tool_use_id":null,"uuid":"assistant-1","session_id":"claude-session-1"}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_read_1","content":"fn main() { println!(\"hello\"); }","is_error":false}]},"parent_tool_use_id":null,"tool_use_result":{"type":"text","file":{"filePath":"/workspace/src/main.rs","content":"fn main() { println!(\"hello\"); }"}},"timestamp":"2026-08-23T08:00:01.420Z","uuid":"user-tool-result-1","session_id":"claude-session-1"}
{"type":"assistant","message":{"id":"msg_final_1","type":"message","role":"assistant","model":"claude-sonnet-4","content":[{"type":"text","text":"This is a minimal Rust program whose main function prints hello to standard output."}],"stop_reason":"end_turn","stop_sequence":null,"usage":{"input_tokens":168,"output_tokens":31,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"parent_tool_use_id":null,"uuid":"assistant-2","session_id":"claude-session-1"}
{"type":"result","subtype":"success","duration_ms":2100,"duration_api_ms":1700,"is_error":false,"num_turns":2,"result":"This is a minimal Rust program whose main function prints hello to standard output.","stop_reason":"end_turn","total_cost_usd":0.001689,"usage":{"input_tokens":288,"output_tokens":55},"modelUsage":{"claude-sonnet-4":{"inputTokens":288,"outputTokens":55,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"costUSD":0.001689,"contextWindow":200000,"maxOutputTokens":64000}},"permission_denials":[],"uuid":"result-1","session_id":"claude-session-1"}
```

The SDK stream does not give every event a uniform timestamp. Local 2.1.237 adds ISO timestamps to `assistant` and `user` messages, but `system`, `api_retry`, and `result` can still omit them. In the fixed source snapshot, the `user` timestamp is optional and consumers are explicitly told to fall back to receive time for older emitters.

### 2.2 Corresponding ATIF

```json
{
  "steps": [
    {
      "step_id": 2,
      "timestamp": "2026-08-23T08:00:01.250Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "I will read the entry-point file first.",
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
      "extra": {"source_message_id": "msg_tool_1", "timestamp_source": "assistant_message_or_receiver"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.100Z",
      "source": "agent",
      "model_name": "claude-sonnet-4",
      "message": "This is a minimal Rust program whose main function prints hello to standard output.",
      "metrics": {"prompt_tokens": 168, "completion_tokens": 31, "cached_tokens": 0},
      "llm_call_count": 1,
      "extra": {"source_message_id": "msg_final_1", "timestamp_source": "assistant_message_or_receiver"}
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

The mapping requires two key operations:

1. Build one model step from each assistant `message.id`.
2. Use `tool_result.tool_use_id` to find the earlier `tool_use.id` and attach the environment result to that ATIF step's `observation`.

`result.total_cost_usd` is Claude Code's whole-run aggregate. It may include auxiliary model calls and is not a billing field directly returned by an Anthropic Messages response. It cannot be proportionally fabricated across the two visible steps. The example therefore writes only `final_metrics.total_cost_usd`, records its source, and leaves per-step `metrics.cost_usd` absent.

---

## 3. Codex: public JSONL is a thread/turn/item projection, with usage aggregated only at turn end

The actual event definitions for Codex `exec --json` are in [`codex-rs/exec/src/exec_events.rs`](../../../references/codex/codex-rs/exec/src/exec_events.rs). The top-level `ThreadEvent` variants are `thread.started`, `turn.started`, `item.started/updated/completed`, `turn.completed/failed`, and `error`.

### 3.1 What Codex ThreadEvent Source Records look like

```jsonl
{"type":"thread.started","thread_id":"codex-thread-1"}
{"type":"turn.started"}
{"type":"item.started","item":{"id":"item_cmd_1","type":"command_execution","command":"sed -n '1,200p' src/main.rs","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_cmd_1","type":"command_execution","command":"sed -n '1,200p' src/main.rs","aggregated_output":"fn main() { println!(\"hello\"); }\n","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_msg_1","type":"agent_message","text":"This is a minimal Rust program whose main function prints hello to standard output."}}
{"type":"turn.completed","usage":{"input_tokens":288,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":55,"reasoning_output_tokens":12}}
```

These public `ThreadEvent` values contain no timestamps. Some begin/end objects in the lower-level Codex protocol have `started_at_ms` and `completed_at_ms`, but the normalized `exec --json` events drop them. If Harbor consumes only stdout JSONL, it can only add receive time while reading each line.

### 3.2 Corresponding ATIF

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
      "message": "This is a minimal Rust program whose main function prints hello to standard output.",
      "llm_call_count": 1,
      "extra": {"source_item_id": "item_msg_1", "timestamp_source": "receiver", "usage_attribution": "unavailable"}
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

This mapping contains genuine information loss: `turn.completed.usage` covers the whole user turn, potentially including multiple model inferences. The public stream provides no per-inference usage that can be assigned reliably to ATIF steps 2 and 3. The correct mapping fills only `final_metrics` and explicitly says attribution is unavailable instead of dividing the aggregate evenly.

---

## 4. OpenCode: events update message parts, and a tool is a state machine

OpenCode's current V2 SDK types are defined in [`packages/sdk/js/src/v2/gen/types.gen.ts`](../../../references/opencode/packages/sdk/js/src/v2/gen/types.gen.ts), while the CLI projection of those events is in [`packages/opencode/src/cli/cmd/run.ts`](../../../references/opencode/packages/opencode/src/cli/cmd/run.ts). The internal core event `message.part.updated` is also exposed through the V2 SDK event protocol, so it is both an internal event type and a Source Record observable at the SDK boundary. Parts include text, tool, step-start, step-finish, and more. `opencode run --format json` projects them again into `step_start/tool_use/step_finish/text` and adds a top-level timestamp.

### 4.1 What OpenCode SDK Source Records (`message.part.updated`) look like

```jsonl
{"id":"evt-1","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472001100,"part":{"id":"part-tool-1","sessionID":"oc-session-1","messageID":"msg-1","type":"tool","callID":"call-read-1","tool":"read","state":{"status":"running","input":{"filePath":"src/main.rs"},"title":"Read src/main.rs","metadata":{},"time":{"start":1787472001090}}}}}
{"id":"evt-2","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472001420,"part":{"id":"part-tool-1","sessionID":"oc-session-1","messageID":"msg-1","type":"tool","callID":"call-read-1","tool":"read","state":{"status":"completed","input":{"filePath":"src/main.rs"},"output":"fn main() { println!(\"hello\"); }","title":"Read src/main.rs","metadata":{},"time":{"start":1787472001090,"end":1787472001418}}}}}
{"id":"evt-3","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472001500,"part":{"id":"part-finish-1","sessionID":"oc-session-1","messageID":"msg-1","type":"step-finish","reason":"tool-calls","cost":0.00072,"tokens":{"input":120,"output":24,"reasoning":0,"cache":{"read":0,"write":0}}}}}
{"id":"evt-4","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472002100,"part":{"id":"part-text-2","sessionID":"oc-session-1","messageID":"msg-2","type":"text","text":"This is a minimal Rust program whose main function prints hello to standard output.","time":{"start":1787472001800,"end":1787472002090}}}}
{"id":"evt-5","type":"message.part.updated","properties":{"sessionID":"oc-session-1","time":1787472002120,"part":{"id":"part-finish-2","sessionID":"oc-session-1","messageID":"msg-2","type":"step-finish","reason":"stop","cost":0.000969,"tokens":{"input":168,"output":31,"reasoning":0,"cache":{"read":0,"write":0}}}}}
```

Reducing this kind of example to only `type` and `part` would hide an important fact: the real current `message.part.updated` envelope has `properties.time`. Assistant messages also have `time.created/completed`, while tool states have `time.start/end`.

### 4.2 Corresponding ATIF

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
      "extra": {"source_message_id": "msg-1", "timestamp_source": "event"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.120Z",
      "source": "agent",
      "message": "This is a minimal Rust program whose main function prints hello to standard output.",
      "metrics": {"prompt_tokens": 168, "completion_tokens": 31, "cached_tokens": 0, "extra":{"estimated_cost_usd":0.000969,"cost_source":"opencode_model_catalog"}},
      "llm_call_count": 1,
      "extra": {"source_message_id": "msg-2", "timestamp_source": "event"}
    }
  ]
}
```

The converter must aggregate parts by `messageID` and associate running and completed tool states by `callID`. `step-finish` provides per-model-step tokens and cost, making the structural projection straightforward. OpenCode currently calculates that cost from model prices and tokens, however; it is not evidence of a provider-returned charge.

---

## 5. Grok: `streaming-json` is a lightweight state stream reduced from ACP updates

Grok's actual `streaming-json` wire definitions are in [`xai-grok-pager/src/headless/reducer/acp.rs`](../../../references/grok-build/crates/codegen/xai-grok-pager/src/headless/reducer/acp.rs), with upstream unified events in the neighboring [`mod.rs`](../../../references/grok-build/crates/codegen/xai-grok-pager/src/headless/reducer/mod.rs). The reducer turns ACP updates into events such as `text`, `thought`, `tool_call`, `tool_call_update`, `usage`, and terminal `end`.

### 5.1 What Grok streaming-json Source Records look like

```jsonl
{"type":"thought","data":"I need to inspect the Rust entry point."}
{"type":"tool_call","toolCallId":"grok-call-1","title":"Read src/main.rs","kind":"read","status":"pending","toolName":"read_file","rawInput":{"path":"src/main.rs"},"content":[],"locations":[{"path":"src/main.rs"}]}
{"type":"tool_call_update","toolCallId":"grok-call-1","status":"completed","content":[{"type":"content","content":{"type":"text","text":"fn main() { println!(\"hello\"); }"}}],"rawOutput":{"text":"fn main() { println!(\"hello\"); }"},"locations":[{"path":"src/main.rs"}]}
{"type":"usage","messageId":"grok-msg-1","stopReason":"tool_use","usage":{"inputTokens":120,"outputTokens":24,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}
{"type":"text","data":"This is a minimal Rust program whose main function prints hello to standard output."}
{"type":"usage","messageId":"grok-msg-2","stopReason":"end_turn","usage":{"inputTokens":168,"outputTokens":31,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}
{"type":"end","stopReason":"EndTurn","sessionId":"grok-session-1","requestId":"grok-request-1","usage":{"input_tokens":288,"output_tokens":55,"total_tokens":343,"num_turns":2}}
```

Neither `AcpLine` nor `AcpUsageLine` has a timestamp field. Event order comes from NDJSON line order, and terminal `end` provides only a run aggregate. Grok internally maintains more session and usage state, but a third party integrating through `streaming-json` cannot assume those internal fields appear on stdout.

### 5.2 Corresponding ATIF

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
      "extra": {"source_message_id": "grok-msg-1", "timestamp_source": "receiver"}
    },
    {
      "step_id": 3,
      "timestamp": "2026-08-23T08:00:02.100Z",
      "source": "agent",
      "message": "This is a minimal Rust program whose main function prints hello to standard output.",
      "metrics": {"prompt_tokens": 168, "completion_tokens": 31, "cached_tokens": 0},
      "llm_call_count": 1,
      "extra": {"source_message_id": "grok-msg-2", "timestamp_source": "receiver"}
    }
  ]
}
```

Grok conversion is a small state machine: accumulate thought and text deltas; create a call on `tool_call`; complete its observation with a `tool_call_update` bearing the same `toolCallId`; then close one model step with `usage.messageId`.

---

## 6. Content differences among the five Source Record formats and ATIF

The examples show that Source Records and ATIF do not preserve wholly different facts. Their content overlaps heavily; the differences lie in organization and completion timing. An adapter should first normalize Source Records faithfully into Native Events rather than fabricate information absent from the source protocol:

| Observable fact | Pi | Claude Code | Codex | OpenCode | Grok | ATIF target |
|---|---|---|---|---|---|---|
| Model-response boundary | `turn_end.message` | Assistant `message.id` | Not directly exposed; inferred from item/turn | `messageID` + `step-finish` | `usage.messageId` | One `source: agent` step |
| Tool-call ID | `toolCallId` | `tool_use.id` | Item `id` | `callID` | `toolCallId` | `tool_calls[].tool_call_id` |
| Tool result | `toolResults` / execution end | `tool_result` | Completed item | Completed ToolPart | Tool-call update | `observation.results[]` |
| Per-call tokens | Yes | Yes | No; turn aggregate only | Yes | Yes | `step.metrics` |
| Per-call cost | Agent-calculated value, usually not provider charge | None on message; result has an agent-reported run aggregate | None | Agent-calculated value | Depends on backend usage | Write `step.metrics.cost_usd` only with reliable provenance; otherwise use `extra` |
| Time | Messages have it; events are inconsistent | Inconsistent | Absent from public stream | Present on events, messages, and tools | Absent from public stream | Optional `step.timestamp` |

ATIF is a **completed-state snapshot**: it expects each step to already contain a complete message, tool calls, observation, and metrics. Native Events are **facts as they happen over time**: a tool starts and later completes; model text may arrive as deltas before completion; cost may even resolve asynchronously after the run. Journal Entries add reliable order and record time to those facts, while the Event Journal preserves the replayable append history. ATIF and the Event Journal can derive from the same facts, but they should not share one write model.

## 7. Concrete recommendations for nanoPyCodeAgent

### 7.1 Journal Entries must provide record time and ordering

Native Events do not need to allocate persistence order themselves. After accepting one, the journal writer wraps it in a uniform Journal Entry:

```json
{
  "schema_version": 1,
  "run_id": "run-123",
  "seq": 17,
  "recorded_at": "2026-08-23T08:00:01.420Z",
  "type": "tool.completed",
  "payload": {
    "tool_call_id": "call-read-1",
    "tool_name": "read",
    "result": "fn main() { println!(\"hello\"); }",
    "is_error": false,
    "duration_ms": 330,
    "source_timestamp": null,
    "timestamp_source": "receiver"
  }
}
```

The semantic constraints should be:

- `schema_version` describes the internal Journal Entry and Native Event contract, not the ATIF schema version.
- `seq` is allocated by the journal writer, strictly increases, and is authoritative ordering within a run.
- `recorded_at` is the UTC wall-clock time when nano accepted or recorded the event, uses RFC 3339/ISO 8601, and is required on every Journal Entry.
- `source_timestamp` belongs to the Native Event payload and is set only when a Source Record provides reliable source time. When absent, keep it `null`; never present `recorded_at` as source occurrence time.
- Precise duration uses `duration_ms` or paired start/end events rather than relying only on subtraction between two wall-clock values.
- ATIF `step.timestamp` prefers reliable `source_timestamp`, otherwise falls back to `recorded_at`, and records the choice in `extra.timestamp_source`.

### 7.2 The minimum Native Event set should cover model, tool, and run terminal states

At minimum, preserve:

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

`model.completed` should retain `message_id`, complete content and tool calls, actual model, stop reason, usage, and provider response or generation ID. Only then can an ATIF converter map each inference without reproducing the information loss of Codex public JSONL, where only turn-level aggregates are available.

### 7.3 The internal Event Journal and the public ATIF Trajectory are different artifacts

Keep an internal Event Journal. The journal writer appends each Journal Entry; the first implementation may encode one Journal Entry per JSONL line. This JSONL is an internal fact log. It defines no steps, observations, or final metrics and is not exposed by `--trajectory`.

Use only ATIF-v1.7 for the public trajectory. The ATIF projector consumes the Event Journal live or replays it later, folding multiple Native Events into completed steps. `--trajectory PATH` points to the ATIF file, not the internal Event Journal. This avoids maintaining both a “native trajectory” and ATIF as separate public trajectory semantics; it does not eliminate internal schemas. Native Events and Journal Entries still have an internal schema, and a one-way Native Event → ATIF projector still requires maintenance.

This is a **later architecture recommendation** derived from the Source Record-to-ATIF comparison. It explicitly supersedes the older proposal in section 8.4 of [`agent_output_and_trajectory.md`](agent_output_and_trajectory.md), where `--trajectory` wrote native trajectory JSONL and the Harbor adapter converted it to ATIF. The stdout `--output-format` contract in that earlier document remains valid; only the public trajectory persistence boundary has changed.

In implementation, the Event Journal can append Journal Entries during the run. At run end or a checkpoint, fold the current facts into complete ATIF and atomically update the `--trajectory` target using a temporary file plus rename. If the process is interrupted, the Event Journal remains complete through its final intact Journal Entry, while ATIF remains at its latest complete snapshot.

## Final answer

Real projects expose no single uniform Source Record. Pi has turn/message/tool records close to internal `AgentEvent`; Claude Code exposes SDK messages; Codex exposes thread items; the OpenCode CLI exposes a public projection of message parts; and Grok exposes a public reduction of ACP updates. An adapter first normalizes these different shapes into nano Native Events, the journal writer then creates Journal Entries, and the ATIF projector finally folds the Event Journal into uniform user and agent steps, tool calls, observations, and metrics.

When a Source Record example has no timestamp, that does not make time unimportant. More precisely, some source protocols have no uniform timestamp, some place time inside message or tool payloads, and the OpenCode CLI adds time at the top level of its public records. nano's journal writer should assign `seq + recorded_at` to every Journal Entry while preserving any available `source_timestamp`. ATIF projection should state which time source it selected. It must neither depend on clocks hidden behind stdout line order nor fabricate source occurrence times merely to make ATIF look complete.
