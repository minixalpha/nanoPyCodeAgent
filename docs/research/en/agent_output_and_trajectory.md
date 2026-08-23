# Run Output, Execution Traces, Task Trajectories, and Session Design in Mainstream Code Agents

> Generated from the Chinese source [`../zh-CN/agent_output_and_trajectory.md`](../zh-CN/agent_output_and_trajectory.md). Do not edit by hand.

Surveyed on 2026-08-22.

[`benchmark_headless_interface.md`](benchmark_headless_interface.md) previously proposed the following interface, but did not explain whether the two parameters control the same kind of artifact:

```text
[--output-format text|stream-json]
[--trajectory <path>]
```

Both parameters appear to concern “output,” but they actually belong to different planes. Before comparing Pi, Claude Code, Codex, OpenCode, and Grok Build, four questions must be answered:

1. What does this agent invocation deliver to a person or calling program?
2. What actually happened inside the agent?
3. How should a benchmark record the path the agent took to complete the task?
4. What state will the agent use to resume context next time?

These questions correspond to **run output, execution trace, trajectory, and session**, respectively. The document first distinguishes the four using one example run, then examines each project's implementation.

---

## 1. Four Artifacts from One Run

Suppose the user asks the agent to:

```text
Fix the exception parser.py raises when tool arguments are empty, and run the relevant tests.
```

A typical execution might read the failing code, search for callers, modify the code, run tests, and finally answer the user. This document calls the bounded period from accepting that prompt until the agent stops autonomous work a **run**. One run may contain multiple model requests and multiple tool calls.

### 1.1 Run Output: Public Output Delivered to the Caller

Run output answers: **“What should this invocation expose externally?”** The caller may be a person at a terminal, a Shell script, a benchmark harness, an SDK, or a UI.

The same result can have different representations. For example, `text` mode may emit only the final answer:

```text
Fixed empty tool-argument parsing and added a regression test. All 12 relevant tests pass.
```

At the end of the run, `json` mode may deliver a machine-readable **single result object**. It summarizes **how this run ultimately ended**, such as its final status, answer, stop reason, usage, and cost. It does not summarize the complete execution process or pack the trace, trajectory, or session into one JSON object:

```json
{"status":"completed","result":"Fixed empty tool-argument parsing and added a regression test. All 12 relevant tests pass.","usage":{"input_tokens":1200,"output_tokens":180}}
```

During the run, `stream-json` mode may publish a stable public event protocol. The example below uses **JSON Lines (JSONL)**, where every non-empty line is one complete JSON object. This format is also commonly called **Newline-Delimited JSON (NDJSON)**; `ND` means `Newline-Delimited`:

```jsonl
{"type":"tool.completed","tool":"pytest","is_error":false,"result":"12 passed"}
{"type":"assistant.message","content":"Fixed empty tool-argument parsing and added a regression test. All 12 relevant tests pass."}
{"type":"run.completed","status":"completed"}
```

Four output-protocol terms recur throughout the rest of this document:

- **Single result object:** one JSON object emitted after the run ends, summarizing the run's final result. Fields vary by product, but commonly include the final answer, completed/failed status, stop reason, run/session ID, turn count, token usage, and cost. It usually does not contain step-by-step execution records.
- **Public event stream:** a stable event protocol that the agent delivers to external callers in occurrence order during a run. It exposes only selected events suitable for long-term compatibility, such as tool starts/ends, complete assistant messages, and run termination. It is not a raw dump of the internal event bus or execution trace. Every CLI event stream examined here uses JSONL/NDJSON: one complete event object per line.
- **Partial and delta:** a `partial` is an intermediate, unfinished state of a message, thinking block, or tool arguments; a `delta` is the small fragment newly added or changed relative to previously emitted content. A protocol may repeatedly emit cumulative partial snapshots, or emit only deltas for the consumer to assemble. The table's “partial / delta capability” asks one question: **does the public event stream expose fragments of logical content before that content is complete?**
- **Terminal event:** a public-stream event that explicitly declares that the run ended with a state such as completed or failed, for example `run.completed` or `result`. It conveys more than EOF: EOF says only that stdout closed, which may result from normal exit, a crash, interruption, or truncation.

Having a public event stream and having partial/delta output are therefore independent capabilities. A stream that emits `tool.completed` only after pytest finishes and then emits a complete `assistant.message` is still real-time, but it has no partial/delta capability. If answer generation instead emits `assistant.delta: "Fixed"` and then `assistant.delta: " successfully"`, it does expose content incrementally. With or without deltas, a normal shutdown can still use a terminal event to state that the entire run has ended.

This document calls stdout's encoding and record boundaries its **transport format (wire format)**: whether stdout contains text, one JSON object, or one JSON object per line, and how records are separated. When the discussion also covers event types, ordering, termination, and error semantics, the document uses **output protocol**.

Even when a public stream includes `tool.completed`, it remains **run output**, because it is an intentionally supported public contract for callers rather than a raw internal trace. **`--output-format` selects how this public output is encoded and framed.** It does not enable traces, save trajectories, or persist sessions.

### 1.2 Execution Trace: Runtime Evidence for Troubleshooting

An execution trace answers: **“What actually happened inside the agent?”** It is intended for agent developers and observability systems. Typical contents include:

- Provider request and response metadata, retries, and backoff.
- Model calls, tool scheduling, subprocesses, concurrent tasks, and timing.
- Complete or redacted tool input/output, stderr, and exception stacks.
- Parent-child span relationships, internal state transitions, and performance data.

A debugging trace might contain facts like these:

```text
inference attempt=1 status=429 retry_after_ms=800
inference attempt=2 request_id=req_2 latency_ms=1430
tool call_id=t1 process_id=4312 stdout_bytes=824 exit_code=0
```

This information can explain latency or failure, but selecting `--output-format stream-json` should not cause all of it to enter stdout. A trace is usually more detailed, more sensitive, and more closely coupled to the current implementation. Its schema generally does not carry the same public compatibility promise as run output.

Logs, metrics, and OpenTelemetry are ways to record or transport diagnostic signals, not additional categories of “user output” parallel to traces. An OpenTelemetry trace is itself one representation of an execution trace.

### 1.3 Trajectory: The Execution Path Retained for Task Evaluation

A trajectory answers: **“Through which observations and actions did the agent obtain this task result?”** It is usually scoped to one benchmark trial or task run and consumed by evaluation frameworks and offline analyzers.

The same run might be organized into this trajectory:

```jsonl
{"step":1,"observation":"parser.py dereferences arguments when they are empty","action":{"tool":"search","query":"parse tool arguments"}}
{"step":2,"observation":"found two callers and one missing null branch","action":{"tool":"edit","file":"parser.py"},"result":"added empty-argument handling"}
{"step":3,"observation":"code updated","action":{"tool":"pytest","target":"tests/test_parser.py"},"result":"12 passed"}
{"outcome":"completed","result":"bug fixed","usage":{"input_tokens":1200,"output_tokens":180}}
```

Trajectories and traces both describe execution, but make different trade-offs:

- A trace stays close to runtime implementation and aims to reconstruct a failure scene. It may include every retry, internal queue, and raw payload.
- A trajectory stays close to task semantics and supports comparison and attribution. It retains analytical fields such as observation, action, tool result, outcome, tokens, and cost.
- A trajectory can be derived from a public event stream, trace, or session, but the converted artifact is the trajectory. Its source data does not change category merely because a trajectory was derived from it.

A trajectory is usually fixed after the run ends. It may support visualization or offline replay, but **replay is not resume**: step records alone do not mean the agent can reconstruct the product state and continue the conversation.

Nor can an entire session export simply be renamed a trajectory. A session may contain multiple runs, earlier tasks, branches, and compaction metadata. An adapter must first isolate the current task/trial boundary and then organize it into observations, actions, and outcomes.

### 1.4 Session: Product State Persisted for Continued Work

A session answers: **“From what state should the next invocation continue?”** It usually outlives a single run and may support continue, resume, fork, rewind, or compaction.

A session may retain:

- Session ID, working directory, model, and tool configuration.
- User messages, assistant messages, tool calls, and results.
- Stable entry/message IDs and parent relationships.
- Compaction checkpoints, branches, permission decisions, and other recovery state.

For example, after ending one process the user might run:

```text
agent --resume s1 -p "Also handle the case where arguments is missing."
```

The agent must reconstruct context from session `s1`. This is the session's defining capability and the boundary between a session and a trajectory: **whether the product can reliably continue, resume, or fork matters more than whether a file is named transcript, history, rollout, or JSONL.**

Codex is the clearest example of how names can mislead. Its persistent session files are named `rollout-*.jsonl`, but `resume` continues them, `fork` derives new sessions from them, and `--ephemeral` disables them. This document therefore classifies a Codex rollout as a **session store**. The separate opt-in `rollout-trace` is the execution trace used for troubleshooting; the two are not the same file.

---

## 2. Classify by Lifecycle and Purpose, Not by Filename

The minimum boundaries among the four concepts are:

| Concept | Core question | Typical lifecycle | Primary consumer | Typical contents | Used for resume | Control plane |
| --- | --- | --- | --- | --- | :-: | --- |
| Run output | What does this invocation deliver externally? | One run | People, scripts, runners, SDKs, UIs | Final answer, public events, status, usage | No | `--output-format` |
| Execution trace | What happened internally at runtime? | One run, process, or trace tree | Developers, observability platforms | Requests/responses, retries, spans, internal tools, exceptions | No | Debug / trace / telemetry configuration |
| Trajectory | How did the agent complete this task? | One task / trial / run | Benchmarks, offline analyzers | Observations, actions, tool results, outcome, cost | Usually no | `--trajectory` or an adapter |
| Session | From what state should the next invocation continue? | Multiple runs | The agent product itself | Recoverable transcript, stable IDs, branches, compaction, configuration | Yes | Session / resume / persistence configuration |

One session can contain multiple runs. Each run produces its own output and may optionally record a trace and trajectory:

```text
session s1
├─ run r1: initial fix task
│  ├─ output o1 ───────────────> current caller
│  ├─ execution trace t1 ──────> debugger / tracing backend
│  └─ trajectory j1 ───────────> benchmark artifact
└─ run r2: follow-up after resume
   ├─ output o2
   ├─ execution trace t2
   └─ trajectory j2
```

Their data overlaps, but their compatibility promises differ. A reasonable implementation can project four artifacts from the same set of internal events. Here, “project” means selecting fields and transforming structure for each purpose, not copying every internal event:

```text
                         ┌─ text renderer ───────────────> stdout
agent loop ─> canonical ├─ final JSON reducer ──────────> stdout
              events     ├─ JSONL event serializer ─────> stdout
                         ├─ trace recorder ──────────────> debug bundle / OTel
                         ├─ trajectory projector ────────> requested artifact
                         └─ session recorder ────────────> session store
```

The first three branches may emit different numbers of records, but all are run output. `--output-format` may select among only those three; it cannot also change trace, trajectory, or session persistence.

---

## 3. Research Scope and Core Conclusions

### 3.1 Evidence Scope

Before beginning the survey, we attempted to update the code under `references/`. The four accessible repositories were fast-forwarded to their latest remote commits. The remote for the third-party Claude Code mirror was no longer accessible, so it was not forcibly replaced.

| Project | Local revision | Update result | Evidence level |
| --- | --- | --- | --- |
| Grok Build | `19d42e35c07a9c9244f03f6df0c4c353f970d4f9` | Updated | Official xAI open-source repository |
| Pi | `c49906ec77788625aacbdc53ebca6fbe65bd20f5` | Updated | Public repository tracked by `references/pi` |
| OpenCode | `e00890c67261a435cee6409366a68999a93393fd` | Updated | Official OpenCode open-source repository |
| Codex | `4f39251a010a8bd7d692d25fb33832ff06f1635a` | Updated | Official OpenAI open-source repository |
| Claude Code | `a371abbe75ffa0d0a3c92290e2bbf56a7ef54367` | Remote returned `Repository not found`; snapshot retained | **Unofficial sourcemap mirror, used only to corroborate implementation ideas** |

The authoritative Claude Code contract is the current Anthropic [CLI reference](https://code.claude.com/docs/en/cli-usage), [headless documentation](https://code.claude.com/docs/en/headless), and [sessions documentation](https://code.claude.com/docs/en/sessions). The local `references/claude-code/README.md` also explicitly states that it is not an official Anthropic project, so this document does not treat internal fields from that snapshot as a current stable API.

### 3.2 Core Conclusions

1. **`--output-format` selects only the stdout representation of public run output.** It is not file redirection and does not control execution traces, trajectories, or sessions.
2. **`text`, `json`, and `stream-json` describe three stdout transport formats.** `text` is final text, `json` is one result object at the end, and `stream-json` is a JSONL/NDJSON event sequence published line by line during the run.
3. **`--trajectory PATH` should be an independent control plane.** When present, it creates a trajectory scoped to the current task run; `PATH` selects only the artifact location and does not change stdout.
4. **A trajectory is not a simplified session.** A trajectory explains a task path for evaluation; a session restores product state. Resume requires a separate design for stable IDs, branches, compaction, and schema migration.
5. **All five surveyed products implement sessions, but none provides a benchmark `--trajectory PATH` exactly equivalent to the interface proposed here.** A benchmark can derive a trajectory from a public event stream or session, but that does not make the source artifact a trajectory.
6. **The name `json` has no uniform industry meaning.** Claude Code and Grok use it for a single result object; Pi, Codex, and OpenCode use it for a JSONL event stream. Documentation must therefore specify stdout's actual transport format and output semantics rather than list enum names alone.

---

## 4. Implementation Overview Across Five Projects

### 4.1 What Is Delivered to the Caller: Text, One Result Object, or an Event Stream

First consider which **run output forms** each product provides. The table compares what actually appears on stdout rather than each product's format names. `—` means the output form is not provided.

| Project | Human-readable text | One result JSON after the run ends | Line-delimited events during the run (JSONL/NDJSON) |
| --- | --- | --- | --- |
| Pi | Print mode | — | `--mode json` |
| Claude Code | `--output-format text` | `--output-format json` | `--output-format stream-json` |
| Codex | `codex exec` default | — | `codex exec --json` |
| OpenCode | `opencode run --format default`, possibly with multiple completed text segments | —; `opencode export` is a separate session-export command | `opencode run --format json` |
| Grok Build | `--output-format plain`, writes text chunks as they are generated | `--output-format json` | `streaming-json`; also has a Messages-compatible stream |

Now consider only the **public event stream** in the third column. The next two properties describe its content granularity and termination behavior; they are not additional output formats.

| Project | Emits unfinished content early (partial / delta) | Explicitly declares the end of the whole run with an in-stream terminal event |
| --- | --- | --- |
| Pi | Yes; `message_update` provides deltas and `message_end` provides the complete message | Yes; `agent_settled`. `agent_end` ends only one low-level run |
| Claude Code | Optional; add `--include-partial-messages` | Yes; `result` |
| Codex | No; there is no public token/text-delta contract | Yes; `turn.completed` / `turn.failed`, except on interruption |
| OpenCode | No; it emits only coarser completion events | No; relies on EOF + exit code |
| Grok Build | Yes; the native stream emits text/thought chunks by default, while the Messages-compatible stream has a separate partial flag | Yes; native success is `end`, native failure is `error`, and the compatibility stream uses `result` |

Three common patterns are visible in these tables:

- Human-facing modes tend to put only the final answer on stdout and send progress and diagnostics to stderr.
- Real-time machine-facing modes almost universally use “one object per line” JSONL rather than a long-lived JSON array.
- None of the products treats `--output-format` as a switch for sessions, traces, or trajectories.

There are also two differences that cannot be inferred from “industry convention”:

- `json` may mean either a single object or JSONL. Claude/Grok use the former; Pi/Codex/OpenCode use the latter.
- “Streaming” may mean only **emitting events immediately as they occur**, or may additionally include text/thinking/tool-argument deltas at different granularities. Claude uses an extra flag to enable raw partials; Grok's native stream already includes text/thought chunks by default, while its extra flag changes only the framing of the Messages-compatible stream. “Streaming” and “token-level” are therefore not the same promise.

### 4.2 Execution Traces, Trajectories, and Sessions

The next table compares the other three planes. “No dedicated trajectory” means there is no stable artifact interface scoped to one benchmark task/run; it does not mean an adapter cannot convert product data into a trajectory.

| Project | Execution trace | Dedicated benchmark trajectory | Session: storage and primary contents |
| --- | --- | --- | --- |
| Pi | Hidden `/debug` can write TUI render lines and the latest messages sent to the model; not a stable headless trace protocol | None; can be derived from the JSON event stream or a session export | JSONL by default; header, messages, model/thinking changes, compaction, branch/custom entries; `id`/`parentId` form a tree and support continue/resume/fork |
| Claude Code | `--debug` / `--debug-file` records diagnostic logs, with separate telemetry support; independent of stdout output format | None; runners such as Harbor can generate one after parsing `stream-json` | Transcript JSONL by default; messages, tool interactions, and recovery metadata; supports continue/resume/fork and optional disabled persistence |
| Codex | Opt-in local `rollout-trace` bundle containing a manifest, raw events, prompts/responses, tool and terminal payloads, and offline reduced state; also OpenTelemetry | None; `rollout` is a session and `rollout-trace` is a debugging trace, neither is a benchmark trajectory interface | `rollout-*.jsonl` by default; session metadata, model-visible messages/reasoning, tool calls/outputs, and other recoverable items; supports resume/fork, disabled by `--ephemeral` |
| OpenCode | Runtime logs and debug subcommands exist; no complete, stable, user-facing execution-trace artifact was found | None; `export` emits a materialized session snapshot | Session/message/part data and durable events/projections in a global SQLite database; supports continue/session/fork, with large tool output optionally stored separately |
| Grok Build | `RUST_LOG` can write diagnostics to stderr and `GROK_LOG_FILE` to a file; internal logs and session trace exports also exist, none controlled by output format | No CLI parameter equivalent to the semantics proposed here | Session directory holds authoritative updates, model chat history, summary/plan/compaction/subagent and other recovery state; supports continue/resume/fork |

The most important point is not that “everyone uses JSONL,” but who consumes each artifact: output is a stable public protocol, a trace is troubleshooting evidence, a trajectory is the task-evaluation path, and a session is product state that can be restored and forked.

---

## 5. Designs by Project

### 5.1 Pi: `json` Is an Event Stream, While the Session Is a Separate Tree-Shaped JSONL

**Run output.**

Pi's headless interface has three modes:

- Print mode: outputs only the final assistant text.
- `--mode json`: outputs a session header, followed line by line by agent/session events.
- `--mode rpc`: stdin and stdout are both JSONL, serving as an input control protocol as well as an output event protocol.

The first line of `--mode json` looks like this:

```json
{"type":"session","version":3,"id":"...","timestamp":"...","cwd":"..."}
```

Subsequent events may include `agent_start`, turn/message/tool lifecycle events, queue updates, compaction, auto-retry, `agent_end`, and `agent_settled`. A `message_update` retains only the delta instead of repeating the complete message accumulated so far; `message_end` is the authoritative final message. This is a good design for controlling stream size: consumers can use deltas for a real-time UI, then reconcile against the final snapshot at the end.

Here, `agent_end` must not be treated as the terminal event for the entire command: it indicates only that one low-level agent run has ended, after which Pi may still auto-retry, auto-compact, or process a queued continuation. `agent_settled` indicates that Pi will not continue automatically; abnormal process termination and external interruption must still be determined by combining EOF with the exit code.

Pi also takes explicit control of stdout: protocol writes go through controlled raw stdout, while other ordinary output is redirected to stderr, and write backpressure is handled. This shows that “machine-mode stdout must not contain logs” is not merely documentation etiquette, but an implementation boundary.

**Session.**

Pi's session is a separate append-only JSONL file. It has a session header plus message, model-change, compaction, branch, and other entries carrying `id` / `parentId`; its history is therefore fundamentally a tree rather than a verbatim copy of stdout events. Switching branches merely moves the current leaf and does not delete the other branch. Compaction changes the active context sent to the model without erasing the original history.

**Execution trace.**

Pi's hidden `/debug` primarily writes TUI render lines and the latest messages sent to the model; it is not a stable headless trace.

**Trajectory.**

Pi has no dedicated benchmark trajectory. An evaluator can select task steps from the JSON event stream or an exported session and convert them into its own trajectory schema.

**Lessons worth adopting:**

- Deltas and final snapshots have clearly separated responsibilities in the stream.
- Session entries have persistent IDs and parents; ephemeral stdout event IDs do not carry recovery responsibilities.
- The stdout guard and backpressure handling are appropriate for any JSONL CLI.
- One drawback is naming the JSONL mode `json`: callers must read the documentation to know it is not a single object.

Source entry points: [JSON event stream documentation](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md), [RPC event reference](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md), [print mode](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/src/modes/print-mode.ts), and [session format](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/session-format.md).

### 5.2 Claude Code: The Clearest Separation of text, json, and stream-json

**Run output.**

Claude Code's public definitions most directly answer this document's naming question:

| Format | stdout transport format |
| --- | --- |
| `text` | Emit the final plain text after completion |
| `json` | Emit **one** result object after completion, containing result, session ID, usage/cost, and other metadata |
| `stream-json` | Emit SDK messages/events line by line during the run, as NDJSON |

By default, `stream-json` means “emit a message or event as soon as it is produced”; it does not automatically mean “emit every token.” Only when `--include-partial-messages` is also specified do raw `stream_event` records appear, containing text, thinking, or tool-input deltas. This separation is worth preserving: many benchmarks need only tool starts/ends, final messages, and usage, and do not need the volume or compatibility cost of token-level events.

It also has two concepts that are easily confused with trajectory but are in fact entirely different:

- `--input-format stream-json` controls stdin; it is not inferred implicitly from the output format.
- `--replay-user-messages` is input-confirmation echoing for duplex clients, not a replay of an old session's execution history into output.

**Session.**

Claude Code saves sessions by default under `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. Continue, resume, and fork operate on this persistent state; stdout's text/json/stream-json setting affects only how the current invocation reports to its parent process. `--no-session-persistence` is also a separate switch.

The local unofficial snapshot shows transcript entries with parent UUIDs, and stores the full contents of large tool results separately on disk while leaving a preview and path in the message. This further demonstrates that a session is a recoverable directed history, not a stdout event log. It also shows that both sessions and streams may contain complete tool arguments, results, and hook stdout/stderr, and must be treated as sensitive data.

**Execution trace.**

`--debug` / `--debug-file` records diagnostic logs independently of output format.

**Trajectory.**

Claude Code has no dedicated trajectory-path parameter. When Harbor parses `stream-json` and generates a benchmark record, it is projecting a trajectory from run output, not renaming the stdout stream as a trajectory.

**Lessons worth adopting:**

- The three output names map one-to-one to stdout transport formats, minimizing ambiguity.
- Partial deltas are a separate capability rather than being inseparably bound to the name `stream-json`.
- The terminal `result` aggregates status, final answer, session ID, turn, and usage/cost, so consumers do not need to scan the entire stream to calculate the final result.
- Session persistence is fully orthogonal to stdout representation.

Authoritative contracts: [CLI reference](https://code.claude.com/docs/en/cli-usage), [headless mode](https://code.claude.com/docs/en/headless), [sessions](https://code.claude.com/docs/en/sessions), and [custom session storage](https://code.claude.com/docs/en/agent-sdk/session-storage).

### 5.3 Codex: Default Text, `--json` JSONL, and Automatically Persisted Rollouts

**Run output.**

`codex exec` does not have `--output-format`:

- In the default mode, only the final answer goes to stdout; other progress, tool information, and logs go to stderr.
- `--json` writes `thread.started`, turn, item, and error events to stdout line by line.
- `-o/--output-last-message FILE` additionally saves the last assistant message; it neither replaces nor redirects stdout.
- `--output-schema FILE` constrains the **content shape** of the model's final answer; it does not change the outer JSONL event protocol.
- `--ephemeral` disables session-rollout persistence.

Codex's public top-level JSONL events include:

```text
thread.started
turn.started
item.started / item.updated / item.completed
turn.completed / turn.failed
error
```

An item's `type` then distinguishes agent messages, reasoning, command execution, file changes, MCP/collaboration tools, web searches, todos, and errors. A successful run normally ends with `turn.completed`, which contains usage; a failed run ends with `turn.failed`. The current interrupted path may have no terminal JSON event, so a reliable runner should still check EOF, exit code/signal, and stderr together.

**Session.**

Ordinary sessions are written automatically to:

```text
$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread-id>.jsonl
```

Each line's outer envelope carries timestamp, ordinal, type, and payload, and every line is flushed after writing. Resume continues appending to the original rollout; fork creates a new thread ID and materializes the inherited history into a new rollout. The persistence policy retains messages, reasoning, tool calls/outputs, and other data needed for recovery, but filters many transient deltas, begin events, warnings, and UI events. A rollout is therefore not a mirror of stdout JSONL either.

**Execution trace.**

Codex separately implements an opt-in `rollout-trace`. Its local bundle stores `manifest.json`, ordered raw events, prompts/responses, tool I/O, terminal output, and payload references, and can reduce them offline into a semantic graph for a debugger. It has an independent `trace_id` while referencing the observed session's `rollout_id`, directly demonstrating that trace identity and session identity should not be conflated.

`rollout-trace` is for local troubleshooting, not resume; OpenTelemetry is yet another observability output.

**Trajectory.**

Codex has no dedicated benchmark trajectory. Neither the session rollout nor `rollout-trace` is a stable benchmark-trajectory interface; evaluators must create a separate projection from public JSONL, the session rollout, or a trace.

**Lessons worth adopting:**

- The default mode strictly enforces “results on stdout, diagnostics on stderr.”
- `--output-last-message` demonstrates that an additional file sink need not change the main output format.
- Rollouts use ordinals, flush line by line, and can repair a torn tail that lacks a final newline.
- JSONL is a public integration surface actually consumed by the SDK, but the schema has no version number, so consumers must still tolerate unknown events, item types, and newly added fields.

Source and authoritative contract entry points: [OpenAI CLI reference](https://developers.openai.com/codex/cli/reference), [exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs), [stdout contract](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/lib.rs), [exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs), [rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs), and [rollout trace](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout-trace/README.md).

### 5.4 OpenCode: run's `json` Is Coarse-Grained JSONL, While Sessions Live in SQLite

**Run output.**

OpenCode's command is:

```text
opencode run --format default|json
```

Here, `json` is again not an aggregate object, but an event shaped as `{type, timestamp, sessionID, ...data}` on each line. The current public stream projects only coarse-grained semantic-boundary events: step starts/finishes, completed text, completed reasoning only with `--thinking`, completed or failed tool uses, and errors. It emits no raw token deltas, does not contain the full user prompt, and has no unified header, schema version, or terminal footer. Normal completion is recognized through stdout EOF plus the process exit code.

The default format writes every completed assistant text part to stdout. A run that uses tools may have multiple text segments before and after tool calls, and `--thinking` additionally includes reasoning. It is therefore human-readable output, but unlike Claude/Codex headless text, it does not strictly promise “stdout contains only one final answer.”

This keeps it very lightweight, but leaves automated consumers with three costs:

1. There is no terminal object, so status, result, and usage cannot be obtained by reading only the last line.
2. The schema is unversioned and is projected ad hoc from internal session events.
3. The name `--format json` does not reveal that it is a stream.

**Session.**

OpenCode's persistence layer differs even more from its CLI stream. Sessions, messages, parts, and internal durable events/projections primarily live in a global SQLite database; `--continue`, `--session`, and `--fork` determine which session is loaded or copied. `opencode export [sessionID]` is a separate command: it writes a materialized session snapshot as one pretty-printed JSON object to stdout, which the user can then redirect with the Shell. It cannot be treated as a final-object mode for `run --format json`.

Large tool outputs have their previews truncated while the full contents are stored in tool-output files under the data directory. Streams, sessions, and exports cannot by default be regarded as having undergone complete secret redaction; `export --sanitize` performs only limited sanitization.

**Execution trace.**

OpenCode has conventional runtime logs and debug subcommands for configuration, LSP, files, snapshots, and related issues, but no public complete execution-trace artifact.

**Trajectory.**

OpenCode has no dedicated benchmark trajectory. The object emitted by `opencode export` remains a session snapshot; only after an adapter converts its task steps into an evaluation schema is the result a trajectory.

**Lessons worth adopting:**

- A CLI stream can project only semantic events useful to integrations instead of exposing every internal event.
- Session storage can be implemented with SQLite while the external transport format remains JSONL.
- The counterexample is that terminal footers and schema versions are cheap, yet substantially reduce the cost of inferring runner state.

Source entry points: [run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts), [session tables](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/core/src/session/sql.ts), and [export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts).

### 5.5 Grok Build: The Most Complete Output Matrix, Plus Multi-Layer Session State

**Run output.**

Grok Build provides four headless formats:

| Format | Semantics |
| --- | --- |
| `plain` | Plain text for humans; writes text chunks directly as they are generated and appends a newline at the end |
| `json` | One aggregate object at the end, containing text, stop reason, session/request ID, turn, usage, and cost only when complete |
| `streaming-json` | Native NDJSON events projected from ACP session updates |
| `streaming-messages-json` | An NDJSON stream compatible with the Anthropic Messages style |

The native stream has event types including text, thought, tool call/update, plan, `available_commands`, `auto_compact_*`, and max-turns; it ends with `end` on success and `error` on failure. It emits text/thought according to ACP chunks by default. The compatibility stream has init, assistant, user, result, and other messages; only this mode can use `--include-partial-messages` to enable Messages stream framing, within which some deltas, such as tool input, may still be coarse-grained one-shot data.

This matrix demonstrates two independent axes of extension:

- **Time axis:** a final result object versus a real-time event stream.
- **Schema axis:** the agent's own semantic events versus a transport format compatible with an external ecosystem.

It also demonstrates the cost of a compatibility layer: the same internal event must maintain two public projections, some internal states cannot be mapped losslessly, and partial framing, usage, errors, and terminal results must each be defined independently. nanoPyCodeAgent does not need to duplicate this complexity before it has a concrete consumer.

**Session.**

Grok stores sessions by default under `~/.grok/sessions/<encoded-cwd>/<session-id>/`, distinguishing at least:

- `updates.jsonl`: the authoritative session updates for restoring the UI/conversation.
- `chat_history.jsonl`: the history sent to the model, not the session source of truth.
- Other state for summaries, plans, rewinds, signals, feedback, compaction, subagents, and more.

The JSONL writer uses owner-only directories, append, and torn-tail repair. Continue/resume/fork operate on this session; output format remains only a stdout selection for the current headless invocation.

**Execution trace.**

In headless mode, `RUST_LOG` can write diagnostics to stderr and `GROK_LOG_FILE` can write them to a file. The product data directory also contains internal logs and session trace exports. These support troubleshooting or session analysis and are not output formats.

**Trajectory.**

Grok Build has no benchmark `--trajectory PATH` equivalent to the semantics proposed here. Evaluators still need to convert a public stream, session, or trace export.

Grok's native `json` / `streaming-json` formats have another rule for usage/cost worth adopting: when the server has not reported the full cost, cost is omitted or marked incomplete rather than writing a missing value as 0. The Messages-compatible stream is constrained by its target schema, so some unknown values still fall back to 0, with the caveat explicitly documented. For nanoPyCodeAgent's own controllable native benchmark protocol, “unknown” and “free” must be separate states.

**Lessons worth adopting:**

- Aggregate JSON and a native event stream coexist, serving simple scripts and real-time runners respectively.
- Graceful termination has an explicit terminal record: `end` for native success, `error` for native failure, and `result` for the compatibility stream.
- Model-input history is separate from product-recovery history, preventing “current context” from being mistaken for “complete trajectory.”
- A compatibility stream should be driven by real integration needs rather than built from the outset.

Source entry points: [headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md), [format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs), [headless writer](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless.rs), and [session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs).

---

## 6. What Exactly Is `stream-json`?

The recommended formal definition of `stream-json` is:

> **A sequence of JSON objects, delimited by LF and written incrementally to stdout in event-occurrence order. Every non-empty line must be one complete JSON object; when the protocol can terminate gracefully, the final record must describe how the run ended. EOF without a terminal record means the stream was interrupted, crashed, or truncated, and the consumer must additionally inspect the exit code/signal.**

For example:

```jsonl
{"schema_version":1,"type":"run.started","run_id":"r1","sequence":0,"timestamp":"2026-08-22T10:00:00.000Z"}
{"schema_version":1,"type":"tool.started","run_id":"r1","sequence":1,"timestamp":"2026-08-22T10:00:01.000Z","tool_call_id":"t1","tool":"bash","arguments":{"command":"pwd"}}
{"schema_version":1,"type":"tool.completed","run_id":"r1","sequence":2,"timestamp":"2026-08-22T10:00:01.050Z","tool_call_id":"t1","is_error":false,"result":"/app"}
{"schema_version":1,"type":"assistant.message","run_id":"r1","sequence":3,"timestamp":"2026-08-22T10:00:02.000Z","message":{"role":"assistant","content":"Done."}}
{"schema_version":1,"type":"run.completed","run_id":"r1","sequence":4,"timestamp":"2026-08-22T10:00:02.010Z","status":"completed","result":"Done.","turns":1,"usage":{"input_tokens":120,"output_tokens":8}}
```

### 6.1 How It Differs from Ordinary JSON

| Dimension | `json` | `stream-json` |
| --- | --- | --- |
| Document boundary | All of stdout is one JSON value | Every non-empty line is one JSON value |
| First parseable point | Usually when the run ends | When the first event is produced |
| Memory | Producer/consumer often must aggregate the final result | Can process line by line with approximately constant space |
| Intermediate state | Usually none | Can include tool, message, usage, error, and other events |
| Artifact after interruption | The entire document may be invalid or may never have been written | Earlier complete lines remain parseable, but the exit code must be consulted to identify abnormal termination |
| Best suited for | Shell scripts and CI reading one result | Runners, real-time UIs, Harbor adapters, and observation of long-running tasks |

This document calls the format **JSON Lines (JSONL)**. It is also commonly called **Newline-Delimited JSON (NDJSON)**. Both names emphasize that newlines delimit records; neither implies that the data must be stored in a file. The recommendation is to use `stream-json` as the CLI enum name and explicitly document JSONL/NDJSON as its transport format.

### 6.2 What It Does Not Automatically Promise

`stream-json` does not automatically imply:

- Token-level output; events may be emitted only for complete messages or tool stages.
- That input is also JSONL; input should be controlled by a separate `--input-format`.
- Automatic saving to a file; the parent process or Shell decides where stdout goes.
- Resume support; recovery requires stable session IDs, persistent entry IDs, context reconstruction, and a compatibility policy.
- A complete audit log; the public stream may intentionally omit prompts, raw provider payloads, secrets, and oversized tool outputs.
- That concatenating all lines yields a valid JSON array. They are simply a sequence of valid JSON values.

If token-level deltas are needed later, the recommendation is to add `--include-partial-messages` as Claude does. Grok likewise demonstrates that native chunks and compatibility framing are two separate layers of capability. Do not burden the first version of `stream-json` with an implicit high-frequency protocol.

---

## 7. What Should `--trajectory PATH` Mean?

None of the five products has a `--trajectory PATH` exactly matching the semantics proposed here. That is not because a session can substitute for a trajectory, but because these products first solve the problem of continuing interactive work: Pi, Claude, Codex, and Grok persist session files or directories, while OpenCode uses SQLite; users continue, resume, or fork by session ID. When a benchmark trajectory is needed, an integration commonly projects it from a public event stream or session.

nanoPyCodeAgent does not currently have such a session system. Under that premise, the recommendation is:

```text
--trajectory PATH
```

It expresses two closely related, non-conflicting things at the same time:

1. **Presence enables:** a trajectory for this run is generated only when the parameter is present.
2. **Value chooses destination:** `PATH` is the file path for that trajectory.

It **should not**:

- Change stdout's destination.
- Implicitly switch the output format to stream-json.
- Capture stderr as well.
- Promise that the file can be resumed directly.
- Double as a session ID or directory.

The following three commands therefore have different meanings:

```bash
# Final text goes to the terminal; no trajectory is saved
nanoPyCodeAgent -p "fix it" --output-format text

# The NDJSON event stream is redirected verbatim by the Shell; it remains only the public stream
nanoPyCodeAgent -p "fix it" --output-format stream-json > events.jsonl

# Final text still goes to the terminal, while the agent independently saves a trajectory
nanoPyCodeAgent -p "fix it" --output-format text --trajectory run.jsonl
```

The JSONL produced by the second and third commands **need not be identical**: the public stream should be stable, small, and safe, while the trajectory may contain more complete attribution fields and truncation metadata. Both should be projected from the same set of canonical internal events to avoid inconsistent facts.

The path contract should also specify:

- `PATH` denotes a file, not a directory.
- Existing files are not overwritten by default, preventing the silent loss of an expensive run; add explicit overwrite semantics separately if needed.
- The file is created as readable and writable by the current user, with target permissions of `0600` on Unix.
- Every record is flushed after writing so a complete prefix remains after a timeout or kill.
- Readers should tolerate a final incomplete line left by a crash, but must not silently ignore a malformed line in the middle.
- `--trajectory -` should not be allowed, because it would make the trajectory compete with the selected stdout formatter for the same protocol channel.

If sessions become **automatically persisted by default** in the future, the semantics should remain separate: `--no-session-persistence` controls whether to save, `--session`/`--resume` control identity, and `--session-path` should be introduced only if overriding the default location is genuinely supported. Do not silently promote today's benchmark trajectory into tomorrow's resume format. Execution traces should likewise be controlled by separate debug/trace configuration rather than borrowing `--trajectory`.

---

## 8. Recommended Contract for nanoPyCodeAgent

### 8.1 CLI

The recommendation is to expand the original two formats to three:

```text
nanoPyCodeAgent [-p PROMPT | --prompt-file PATH | stdin]
                [--max-turns N]
                [--output-format text|json|stream-json]
                [--trajectory PATH]
```

| `--output-format` value | stdout contract | Typical consumer |
| --- | --- | --- |
| `text` (default) | Final assistant text only; an empty result may produce empty stdout | Humans and the simplest benchmark runners |
| `json` | Exactly one result object after run initialization; preflight failure may leave stdout empty; no interspersed logs | Shell, CI, one-off scripts |
| `stream-json` | One event per line; graceful termination ends with a terminal event, otherwise EOF + nonzero exit/signal denotes an aborted stream | Harbor adapters, SDKs, real-time UIs |

`--trajectory PATH` does not belong in the output-format table. It leaves the stdout contract above unchanged and separately writes incremental JSONL for benchmarks, offline statistics, and failure attribution.

Diagnostics, retry notices, tracebacks, and human-facing progress must all go to stderr. The original API error may still appear on stderr to satisfy Harbor's error-classification requirements; machine-mode stdout must remain parseable at all times.

### 8.2 Single `json` Result Object

It should contain at least:

```json
{
  "schema_version": 1,
  "run_id": "r1",
  "status": "completed",
  "result": "Done.",
  "stop_reason": "end_turn",
  "turns": 3,
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 240
  }
}
```

`status` should express the agent-level result, such as `completed`, `max_turns`, `timeout`, or `failed`. It is a different dimension from the process exit code: following the conclusion in [`benchmark_headless_interface.md`](benchmark_headless_interface.md), a state such as `max_turns`, where “the trial finished normally but the task may not have been completed,” can still exit 0. Invalid arguments, missing credentials, and API/infrastructure failures that prevent further progress should exit nonzero.

The protocol's starting boundary must also be explicit: if **preflight** work such as CLI argument parsing, configuration loading, or credential checks fails before run/writer initialization, stdout may remain empty while diagnostics go to stderr and the process exits nonzero. Once a `run_id` has been created and the protocol emitted or prepared, every failure that can still be reported should, in `json` mode, output the single `status: "failed"` result and, in `stream-json` mode, gracefully emit `run.failed`. A process crash or external forced termination may still leave no result object or footer.

When usage/cost is missing, omit it or explicitly mark `usage_incomplete: true`; do not substitute 0 for unknown. Grok's completeness rule is better suited to benchmarks here than “always fill every cell in a numeric table.”

If `--output-schema PATH` is added in the future, it should constrain the semantic contents of `result` rather than change the outer structure of the CLI result object. Codex and Grok both separate “structured model answer” from “CLI output protocol,” which is the correct boundary.

### 8.3 Minimal `stream-json` Event Set

The first version does not need to reproduce every event from all five projects. The recommended minimum set is:

```text
run.started
assistant.message
tool.started
tool.completed
usage
run.completed
run.failed
```

The public envelope for every record should contain:

| Field | Purpose |
| --- | --- |
| `schema_version` | Make compatibility boundaries explicit; avoid repeating the mistakes of several unversioned public streams |
| `type` | Discriminator that consumers dispatch on permissively |
| `run_id` | Correlate records from the same process run |
| `sequence` | Monotonically increasing, to detect omissions, ordering problems, and truncation |
| `timestamp` | Wall-clock attribution; elapsed time should preferably be calculated with a monotonic clock and then recorded as duration |
| `turn` | Optional; associate the event with a model turn |
| `message_id` / `tool_call_id` | Optional; correlate started/completed records |

Protocol rules:

- Unknown types and newly added fields must be ignorable; within the same major `schema_version`, only backward-compatible extensions are allowed.
- Every tool that reaches a semantic terminal state emits `tool.completed`, whether it succeeded or failed, and carries `is_error`; if the process is interrupted, an already emitted `tool.started` may have no matching terminal event.
- The final record of a normal run that can terminate gracefully is `run.completed`; the final record of an internal failure that can be reported is `run.failed`.
- Interruptions, signals, OOM, serialization failures, and write failures may leave no footer. Receiving a terminal event confirms protocol-level completion; without one, EOF must be interpreted together with the exit code/signal as an abort, crash, or truncation.
- Oversized tool output records should include a preview, original size, and truncated flag; storing the full text separately requires an explicit path and cleanup policy.
- Token deltas can be added later through `assistant.delta` or a partial flag; `assistant.message` must not mean both a delta and a final snapshot.

### 8.4 Trajectory Contents and Stability

The purpose of a trajectory is to “explain why this run produced this result.” At minimum, it should support reconstruction of:

- The input task and a summary of the run configuration.
- Each turn's model completion message or a safely filtered response.
- Tool names, arguments, results, errors, and durations.
- Stop reason, turns, usage/cost, and completeness markers.
- The occurrence of compaction/truncation and the size of omitted contents.
- Final status and result.

The first version should, however, be explicitly labeled: **for benchmark/analysis use, not an execution trace or resumable session.** It need not collect every debugging detail such as provider retries, internal queues, and exception stacks; those belong in an execution trace. Resume support additionally requires stable parent/entry IDs, branch semantics, model/tool configuration migration, post-compaction context recovery, and long-term schema migration. The session implementations in Pi, Claude, Codex, OpenCode, and Grok all show that this is far more than “read the JSONL back and continue.”

When Harbor requires ATIF, the recommendation is to convert the native trajectory into ATIF at the adapter layer instead of making the agent loop depend directly on a benchmark schema. Only if Harbor becomes the sole primary consumer would it be worth considering ATIF directly as the persistent format.

### 8.5 Security and Data Volume

The traces, trajectories, sessions, and public streams of all five projects may store or emit user prompts, reasoning, tool arguments, file contents, command output, environment paths, and provider metadata. Some projects sanitize recognizable secrets from commands or truncate large results, but none provides a universal guarantee that all secrets are removed.

The trajectory should therefore be treated as a sensitive file:

- Use owner-only permissions.
- Explicitly warn in the documentation not to upload raw trajectories.
- Redact API keys, Authorization headers, and recognized credentials before writing.
- Represent large outputs with a bounded preview plus size/hash/truncation metadata.
- If full contents spill to disk, use a directory with the same permissions and define a retention period.
- Make the public `stream-json` more conservative by default than the local trajectory.
- Do not disguise “missing/truncated” as an empty string or 0.

---

## 9. Final Recommendation

The final boundaries among the four concepts introduced at the beginning are:

```text
--output-format text|json|stream-json
```

**Specifies the encoding/representation of stdout.** It neither accepts a path nor handles file redirection.

```text
--trajectory PATH
```

**The presence of the parameter enables an independent trajectory writer, while PATH specifies the location of that trajectory file.** It does not change stdout. Because nanoPyCodeAgent does not currently persist trajectories by default, this is not “changing an existing default path.”

```text
json
```

**Once the run has been initialized, emits one JSON object at the end; a preflight failure before initialization may produce empty stdout and a nonzero exit.**

```text
stream-json
```

**Emits NDJSON during the run: one complete event object per line; on graceful termination, the last line is a terminal result, while abnormal termination may leave only a complete, still-parseable prefix.** Its difference from `json` is “one final snapshot” versus “an incrementally consumable event sequence,” not “whether output is written to a file.”

```text
execution trace
```

**Enabled through separate debug/trace configuration for troubleshooting and observability.** It may be more detailed and sensitive than public output and trajectories, and it does not promise resume support.

```text
session
```

**Managed through separate persistence/session/resume interfaces for continuing, forking, and compacting work across runs.** Codex's `rollout-*.jsonl` belongs to this category; the word rollout in its filename does not make it a trajectory.

These definitions follow the clear naming of Claude Code and Grok most closely, while incorporating Pi's delta/final separation, Codex's stdout/stderr boundary and additional file sink, OpenCode's semantic projection, and the common design across all projects of separating sessions from public event streams.

---

## 10. Reference Entry Points

- Pi: [usage](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/usage.md), [JSON event stream](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md), [RPC events](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md), [sessions](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/sessions.md)
- Claude Code: [CLI reference](https://code.claude.com/docs/en/cli-usage), [headless mode](https://code.claude.com/docs/en/headless), [sessions](https://code.claude.com/docs/en/sessions), [session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)
- Codex: [OpenAI CLI reference](https://developers.openai.com/codex/cli/reference), [exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs), [exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs), [rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs), [rollout trace](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout-trace/README.md)
- OpenCode: [run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts), [export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts)
- Grok Build: [headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md), [format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs), [session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs)
