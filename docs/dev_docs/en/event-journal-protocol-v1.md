# Event Journal Implementation Protocol v1

> Generated from the Chinese source
> [`../zh-CN/event-journal-protocol-v1.md`](../zh-CN/event-journal-protocol-v1.md).
> Do not edit by hand.

| Item | Value |
|---|---|
| Status | Implemented |
| Protocol version | v1 |
| `schema_version` | `1` |
| Visibility | Internal protocol; not a public Run Output or ATIF interface |
| Domain terminology | [`CONTEXT.md`](../../../CONTEXT.md) |
| Core implementation | [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py) |
| Event production and text projection | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| Behavioral tests | [`test_event_journal.py`](../../../tests/test_event_journal.py), [`test_agent.py`](../../../tests/test_agent.py) |

## Document classification

This is an **implemented protocol specification**, not an RFC.

- An RFC is for a proposal, discussion, and review before implementation or a
  behavioral change.
- An ADR records the decision and rationale for an architectural choice that is
  costly to reverse, surprising, or carries significant tradeoffs.
- This document fixes the wire contract, event semantics, persistence behavior,
  and compatibility boundary that are already implemented.

A future behavior change may begin with an RFC or ADR. Once accepted and
implemented, that change must also update this document and the protocol version.

The terms MUST, SHOULD, and MAY denote protocol requirements, recommendations,
and permitted behavior. Unless stated otherwise, fields and validation rules
describe `schema_version = 1`.

## Goals and boundaries

The Event Journal preserves replayable internal runtime facts for one **Agent
Run**. The complete path is:

```text
Agent core
    ↓ produces
Native Event {type, payload}
    ├─→ live projector → existing stdout text Run Output
    └─→ journal writer → Journal Entry
                           ↓ append-only UTF-8 JSONL
                       Event Journal
                           ↓ future projector (outside v1)
                       ATIF Trajectory / other public representations
```

The boundaries are:

- A **Native Event** is an agent-independent runtime fact.
- A **Journal Entry** adds the identity, ordering, and recording time required
  to persist a Native Event.
- An **Event Journal** is the append sequence of Journal Entries for one Agent
  Run.
- stdout is a live text projection of the same Native Events, but it is not the
  Event Journal.
- ATIF, `stream-json`, and other public output projections are outside v1.

The Event Emitter MUST append an event to the Journal before sending it to a
live projector. Persistence truncation applies only to the Journal Entry. The
projector receives the untruncated Native Event, so Journal size limits do not
change existing stdout behavior.

## Encoding and basic types

- A file is UTF-8 JSONL. Every complete line contains exactly one Journal Entry
  and ends with `\n`.
- The writer uses compact JSON. Object field order has no semantics.
- A payload MUST be a JSON object. Its recursive values are limited to `null`,
  booleans, finite numbers, strings, arrays, and objects.
- Non-standard JSON values such as `NaN`, positive or negative infinity, and
  Python objects MUST be rejected.
- All timestamps use RFC 3339 UTC and end in `Z`, for example
  `2026-08-23T08:00:01.420Z`.
- `duration_ms` is a non-negative number in milliseconds. It is computed from
  a monotonic clock interval and is not used for event ordering.

## Journal Entry envelope

Each JSONL line has this top-level shape:

```json
{
  "schema_version": 1,
  "run_id": "run-7d9e81d0-2dbe-4d4c-a473-62582e5dc842",
  "seq": 4,
  "recorded_at": "2026-08-23T08:00:01.420Z",
  "type": "tool.completed",
  "payload": {
    "model_call_id": "model-bb7241c2-348d-4bb6-975a-b33f05ce76b2",
    "tool_call_id": "toolu_01Abc",
    "tool_name": "read",
    "result": "file contents",
    "is_error": false,
    "duration_ms": 3.72,
    "source_timestamp": "2026-08-23T08:00:01.419Z",
    "timestamp_source": "core"
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | The Journal Entry wire-schema version. Fixed at `1` in v1. |
| `run_id` | non-empty string | The Agent Run identity. All entries in one file MUST match. |
| `seq` | positive integer | The authoritative order within a run. The writer begins at `1` and increments once per entry. |
| `recorded_at` | RFC 3339 UTC string | Wall-clock time when the Journal writer accepted and recorded the fact. It is not the ordering key. |
| `type` | string | Native Event type. v1 accepts only the types in this document's event catalog. |
| `payload` | object | Facts belonging to the event. |
| `truncation` | object, optional | Present only when persistence truncated a string. See “Truncation protocol.” |

`seq` is the only authoritative ordering key within a run. `recorded_at` values
may be equal or affected by wall-clock adjustments, so consumers MUST NOT
reorder entries solely by timestamp.

## Time fields shared by all events

Every v1 event payload contains:

| Field | Required | Type | Meaning |
|---|---:|---|---|
| `source_timestamp` | yes | RFC 3339 UTC string or `null` | When the fact occurred or was observed at its source. nano core writes current UTC; an adapter that cannot recover a trustworthy source time may write `null`. |
| `timestamp_source` | no | non-empty string | The source of `source_timestamp`. nano core currently writes `"core"`. |

`source_timestamp` belongs to the Native Event, while `recorded_at` belongs to
the Journal Entry. They describe different stages and cannot substitute for one
another.

## Event catalog

v1 supports nine event types:

| Event | Semantics |
|---|---|
| `run.started` | The Agent Run exists and its execution parameters are fixed. |
| `user.message` | The entry user message for this Agent Run. |
| `model.started` | One model call has begun. |
| `model.output_delta` | The model streamed one text fragment. |
| `model.completed` | One model call completed successfully and its final message and usage are available. |
| `tool.started` | One tool call began. |
| `tool.completed` | One tool call ended with a normal result, a tool-level error, or an exception. |
| `run.completed` | The Agent Run ended normally, including turn-budget exhaustion. |
| `run.failed` | The Agent Run failed because of an unhandled exception. |

### `run.started`

| Field | Type | Meaning |
|---|---|---|
| `mode` | `"interactive"` or `"headless"` | The run mode. |
| `model` | non-empty string | Requested model identifier. |
| `max_turns` | positive integer or `null` | Maximum number of model-call turns; currently `null` in interactive mode. |

This MUST be the first event produced by nano core. It says that the Agent Run
has begun, not that a model request has already been sent.

### `user.message`

| Field | Type | Meaning |
|---|---|---|
| `message_id` | non-empty string | Local identity generated by nano for the entry user message. |
| `content` | any JSON value | User content for this run. The current CLI produces a string; the protocol permits structured content. |

In interactive mode, each user input creates a new Agent Run and Journal. Prior
conversation remains in process as model context, but the new Journal does not
copy it as a complete request snapshot and v1 has no session link.

### `model.started`

| Field | Type | Meaning |
|---|---|---|
| `model_call_id` | non-empty string | Local correlation ID generated by nano for one model call. |
| `model` | non-empty string | Model identifier requested for this call. |

An Agent Run may contain multiple model calls. Each one receives a new
`model_call_id`.

### `model.output_delta`

| Field | Type | Meaning |
|---|---|---|
| `model_call_id` | non-empty string | The associated model call. |
| `delta` | string | Text added by this streaming callback; it may be empty. |

This event represents text deltas only. A tool-only response may have no delta.
The complete text also appears in a text block in the following
`model.completed.content`. This intentional duplication preserves both the
real-time process and the final completed state.

### `model.completed`

| Field | Type | Meaning |
|---|---|---|
| `model_call_id` | non-empty string | Associated local model-call ID. |
| `message_id` | non-empty string | Stable identity of the completed message; the provider response ID is preferred, falling back to `model_call_id`. |
| `content` | array | Complete provider-neutral message blocks; see the schema below. |
| `tool_calls` | array | Ordered copies of all `tool_call` blocks in `content`; they MUST match item by item. |
| `model` | non-empty string | Actual model returned by the provider, falling back to the requested model. |
| `stop_reason` | string or `null` | Provider stop reason, such as `end_turn` or `tool_use`. |
| `usage` | object or `null` | Token usage for this model call; see the schema below. |
| `provider_response_id` | non-empty string or `null` | Original provider response/message ID. |
| `generation_id` | non-empty string or `null` | Provider generation ID, currently read from the `x-generation-id` response header. |
| `duration_ms` | non-negative number | Time from starting the request until the complete message and response headers are available. |

`content` supports these blocks:

| `type` | Other fields | Meaning |
|---|---|---|
| `text` | `text: string` | A complete text fragment. |
| `tool_call` | `tool_call_id: non-empty string`, `tool_name: non-empty string`, `input: object` | A provider-neutral tool call. |
| `extension` | `namespace: non-empty string`, `source_type: string \| null`, `value: JSON value` | A provider block that has not been normalized. nano's Anthropic adapter uses `namespace: "anthropic"`. |

An unknown provider block MUST be wrapped in `extension`; it must not be
silently dropped or represented by inventing another `content.type`.

When `usage` is not `null`:

| Field | Required | Type | Meaning |
|---|---:|---|---|
| `input_tokens` | yes | non-negative integer | Input tokens reported by the provider. |
| `output_tokens` | yes | non-negative integer | Output tokens reported by the provider. |
| `cache_read_input_tokens` | no | non-negative integer | Input tokens read from the prompt cache. |
| `cache_creation_input_tokens` | no | non-negative integer | Input tokens written to the prompt cache. |

Other JSON usage fields returned by the provider MAY be preserved. v1 does not
derive cost from usage or a price catalog.

### `tool.started`

| Field | Required | Type | Meaning |
|---|---:|---|---|
| `tool_call_id` | yes | non-empty string | Provider tool-call ID, matching `model.completed.tool_calls[].tool_call_id`. |
| `tool_name` | yes | non-empty string | Tool name. |
| `input` | yes | object | Complete tool input. |
| `model_call_id` | core profile | non-empty string | Model call that produced this tool call. nano core always writes it; the base v1 payload validator permits omission for normalized sources. |

The same tool call appears in both `model.completed.tool_calls` and the tool
lifecycle events. The former preserves the model action; the latter preserves
the actual execution boundary.

### `tool.completed`

| Field | Required | Type | Meaning |
|---|---:|---|---|
| `tool_call_id` | yes | non-empty string | Same value as the corresponding `tool.started`. |
| `tool_name` | yes | non-empty string | Tool name. |
| `result` | yes | string or `null` | Text returned to the model; `null` when execution raises an exception. |
| `is_error` | yes | boolean | Whether the result represents an error. An expected tool failure may still have a string result and set this to `true`. |
| `duration_ms` | yes | non-negative number | Tool execution duration. |
| `error` | conditionally | object | Required when `result` is `null`. nano core writes `{ "type": ..., "message": ... }`. |
| `model_call_id` | core profile | non-empty string | Model call that produced this tool call; nano core always writes it. |

An expected tool error ends with `tool.completed`, and the agent may continue by
sending the result back to the model. An unhandled tool exception first produces
`tool.completed` with `result: null` and `is_error: true`, then causes the run to
produce `run.failed`.

### `run.completed`

| Field | Type | Meaning |
|---|---|---|
| `outcome` | `"completed"` or `"max_turns_exhausted"` | Normal completion reason. Turn-budget exhaustion is an explainable terminal state, not an exception. |
| `duration_ms` | non-negative number | Total Agent Run duration. |

When the final model reply still requests tools but `max_turns` is exhausted,
core does not execute those tools and directly records `max_turns_exhausted`.

### `run.failed`

| Field | Type | Meaning |
|---|---|---|
| `error_type` | non-empty string | Python type name of the unhandled exception. |
| `message` | string | Exception message; it may be empty. |
| `duration_ms` | non-negative number | Time from run start until failure. |

After `run.failed` is recorded, the original exception continues to propagate to
the caller. CLI argument errors, settings-loading failures, and missing API
credentials happen before an Agent Run is established, so they have no Journal
and do not produce `run.failed`.

## nano core event ordering

Core currently guarantees these typical sequences:

```text
# Successful run without tools
run.started
user.message
model.started
model.output_delta *
model.completed
run.completed(outcome = completed)

# Successful run with tools
run.started
user.message
model.started
model.output_delta *
model.completed(stop_reason = tool_use)
(tool.started → tool.completed) *
model.started
...
run.completed(outcome = completed)

# Model or runtime exception
run.started
user.message
...
run.failed
```

Here `*` means zero or more occurrences. A run MUST end with exactly one of
`run.completed` or `run.failed`; a failed model call does not produce
`model.completed`.

These are state-machine guarantees of the nano core producer. v1 `replay()`
currently validates only each entry's schema, a single `run_id`, and strictly
increasing `seq`; it does not perform cross-event state-machine validation.
Consumers must not equate “the file can be replayed” with “the lifecycle is
complete.” A forcibly terminated process may have no terminal event.

## Identity and correlation rules

- `run_id` currently has the form `run-<UUID>` and determines the filename.
- `message_id` identifies a complete user or model message.
- `model_call_id` correlates `model.started`, all its deltas,
  `model.completed`, and tool events triggered by that reply.
- `tool_call_id` correlates the model action, `tool.started`, and
  `tool.completed`.
- Local IDs need only be stable and non-empty in their applicable scope.
  Consumers SHOULD NOT parse UUID formatting for semantics.

## Truncation protocol

A Journal may contain very large model text, tool input, and tool output. The
writer independently limits every string in the payload, by default to `100000`
Unicode code points:

- Only the persisted copy keeps the string prefix.
- The original Native Event and live stdout projector remain untruncated.
- A truncated Journal Entry gains a top-level `truncation` object:

```json
{
  "fields": [
    {
      "path": "/result",
      "original_chars": 150000,
      "retained_chars": 100000
    }
  ]
}
```

`path` is a JSON Pointer rooted at `payload`. Array indexes use decimal notation;
`~` and `/` in object keys are escaped as `~0` and `~1`. `original_chars` and
`retained_chars` count Python Unicode characters, not UTF-8 bytes.

The following identity, classification, and time metadata fields are not
truncated, preserving correlation and schema validity:

```text
error_type, generation_id, message_id, mode, model, model_call_id,
outcome, provider_response_id, source_timestamp, stop_reason,
timestamp_source, tool_call_id, tool_name
```

Truncation means that the Journal has lost the tail of that field. Consumers
MUST NOT treat the retained prefix as a complete value.

## Storage and append semantics

The default location is:

```text
~/.nanoPyCodeAgent/journals/<run_id>.jsonl
```

The protocol and implementation impose these constraints:

- One Agent Run corresponds to one file.
- `run_id` MUST match `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, preventing directory
  traversal.
- The writer opens files in create-exclusive, append-only mode. It fails rather
  than overwriting an existing file.
- On supported platforms, close-on-exec and no-follow flags are also used.
- The configuration root and Journal directory are set to mode `0700`; files
  are set to mode `0600`.
- A lock serializes append and close operations within one `EventJournal`
  instance.
- A write loop completes each record, and the next `seq` advances only after a
  complete write.
- A normal close calls `fsync` before closing the descriptor.

v1 provides no automatic rotation, retention policy, encryption, compression,
cross-process writer coordination, or Journal management CLI.

## Replay behavior

`EventJournal.replay(path)` returns Journal Entries in file order and enforces:

- Every newline-terminated record MUST be a valid UTF-8 JSON object.
- `schema_version` MUST be the reader-supported value `1`.
- The entry envelope and Native Event payload MUST pass v1 validation.
- All complete entries MUST have the same `run_id`.
- `seq` MUST be a positive integer and strictly increasing. The reader permits
  gaps, while the writer normally produces `1, 2, 3, ...` continuously.
- A final fragment without a newline is treated as a partial tail left by an
  interrupted final write and is ignored.
- A corrupt line in the middle of the file, or any invalid newline-terminated
  final line, MUST raise an error and cannot be skipped.

Replay does not repair the file or validate a state machine, digest, signature,
or tamper-evident chain. “Replayable” means that completely written,
schema-valid facts can be recovered; it does not make the Event Journal a
transactional database or trusted audit log.

## Sensitive information and data scope

The Journal explicitly records:

- the current user input;
- complete model output, streaming text, and tool calls;
- complete tool input and the tool result returned to the model;
- provider message/generation IDs, stop reason, and usage; and
- error type, error message, and stage durations.

It may therefore contain source code, paths, credentials, or other secrets
indirectly through prompts, model output, shell commands, file content, or tool
results. Modes `0700` and `0600` provide only minimum local access control; they
do not provide redaction, encryption, or secret scanning. Journals MUST NOT be
uploaded, published, or shared as ordinary diagnostic attachments by default.

v1 does not explicitly record:

- API keys or authentication headers;
- complete provider requests, HTTP headers, or raw SDK responses;
- the system prompt or a complete history snapshot sent to the model;
- stdout presentation details such as spinners, ANSI color, prompts, or banners;
- token cost or price-catalog resolution;
- session identity or parent-child relationships across runs; or
- an ATIF trajectory or public `stream-json` record.

“No explicit field” does not mean that equivalent data cannot appear inside
content. For example, a secret placed in a shell command is still recorded in
`tool.started.input`.

## stdout and public-interface boundary

When v1 introduced the Event Journal, the existing stdout text had to remain
byte-for-byte behaviorally unchanged. The current `_TextOutputProjector`
consumes only:

- `model.output_delta` to print the reply prefix and streaming text;
- `model.completed` to add a newline after a response that emitted text;
- `tool.started` to print the tool-call preview; and
- `tool.completed` to print a string result.

The Journal path, run ID, recording timestamp, and other envelope metadata are
not written to stdout. The Event Journal is internal reconstruction data, not a
stable user-output contract. External programs SHOULD NOT treat
`~/.nanoPyCodeAgent/journals/*.jsonl` as a public CLI API.

## Versioning and compatibility

A v1 reader fails closed on an unknown `schema_version` or event type. The
compatibility rules are:

- An optional payload field that does not change existing meaning MAY be added
  while retaining `schema_version = 1`; an old reader ignores semantics it does
  not understand.
- Provider-specific model content SHOULD use an `extension` block instead of a
  new block type.
- Adding an event type or required field, changing a field type or meaning, or
  changing the envelope or ordering rules MUST increment `schema_version`.
- A version increment MUST update both language versions of this protocol, the
  producer, reader/replay implementation, and contract tests together.
- Unknown top-level fields are currently ignored by the reader, but are not
  guaranteed to survive deserialize/serialize. Extensions SHOULD live in a
  payload or `extension` block with explicit ownership.

Event Journal v1 is an internal protocol and does not promise permanent
compatibility across nanoPyCodeAgent major versions. `schema_version` exists so
that incompatible changes are rejected explicitly rather than silently
misinterpreted.

## Implementation map

| Behavior | Location |
|---|---|
| Event types, payload validation, and content/usage schemas | [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py) |
| Journal Entry encoding, truncation, permissions, append, fsync, and replay | [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py) |
| Run, user, model, and tool event emission | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| Anthropic block normalization into provider-neutral content | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| Native Event projection into existing stdout text | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| Envelope, ordering, permissions, truncation, partial-tail, and schema tests | [`test_event_journal.py`](../../../tests/test_event_journal.py) |
| Event lifecycle and stdout regression tests | [`test_agent.py`](../../../tests/test_agent.py) |
