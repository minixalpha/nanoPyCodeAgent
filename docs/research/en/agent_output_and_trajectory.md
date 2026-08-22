# Output Formats and Trajectory Design in Mainstream Code Agents

> Generated from the Chinese source [`../zh-CN/agent_output_and_trajectory.md`](../zh-CN/agent_output_and_trajectory.md). Do not edit by hand.

Surveyed on 2026-08-22.

[`benchmark_headless_interface.md`](benchmark_headless_interface.md) previously proposed the following interface, but did not fully define the wire protocol for each parameter:

```text
[--output-format text|stream-json]
[--trajectory <path>]
```

This document works backward from the current implementations of Pi, Claude Code, Codex, OpenCode, and Grok Build to determine how these concepts should be separated. The conclusions come first:

1. **`--output-format` selects the stdout representation; it is not file redirection.** Writing to a file remains the responsibility of the Shell's `>` operator or another explicit file parameter.
2. **For nanoPyCodeAgent, the most natural semantics for `--trajectory PATH` are “enable trajectory recording and write it to PATH.”** It changes neither stdout nor `--output-format`.
3. **`stream-json` should be defined as an NDJSON/JSONL event stream: every line is a complete, independently parseable JSON object.** It is not “one JSON document split into chunks,” nor does it inherently promise token-level increments.
4. **The name `json` has no uniform industry meaning.** Claude Code and Grok use it to mean “emit one object at the end,” while Pi, Codex, and OpenCode use it to mean a JSONL event stream. Interface documentation must therefore specify the wire protocol rather than merely list enum names.
5. **The stdout event stream, persistent session, debugging trace, benchmark trajectory, and telemetry are five distinct artifacts.** They can originate from the same internal event model, but should not share one ambiguous switch.

---

## 1. Research Scope and Evidence Levels

Before beginning the survey, we attempted to update the code under `references/`. The four accessible repositories were fast-forwarded to their latest remote commits. The remote for the third-party Claude Code mirror was no longer accessible, so it was not forcibly replaced.

| Project | Local revision | Update result | Evidence level |
| --- | --- | --- | --- |
| Grok Build | `19d42e35c07a9c9244f03f6df0c4c353f970d4f9` | Updated | Official xAI open-source repository |
| Pi | `c49906ec77788625aacbdc53ebca6fbe65bd20f5` | Updated | Public repository tracked by `references/pi` |
| OpenCode | `e00890c67261a435cee6409366a68999a93393fd` | Updated | Official OpenCode open-source repository |
| Codex | `4f39251a010a8bd7d692d25fb33832ff06f1635a` | Updated | Official OpenAI open-source repository |
| Claude Code | `a371abbe75ffa0d0a3c92290e2bbf56a7ef54367` | Remote returned `Repository not found`; snapshot retained | **Unofficial sourcemap mirror, used only to corroborate implementation ideas** |

The authoritative Claude Code contract is the current Anthropic [CLI reference](https://code.claude.com/docs/en/cli-usage), [headless documentation](https://code.claude.com/docs/en/headless), and [sessions documentation](https://code.claude.com/docs/en/sessions). The local `references/claude-code/README.md` also explicitly states that it is not an official Anthropic project, so this document does not treat internal fields from that snapshot as a current stable API.

---

## 2. First Separate Five Easily Confused Concepts

A headless agent commonly needs all five output categories below. Their data overlaps, but their lifecycles, audiences, and compatibility promises differ.

| Plane | Primary consumer | Typical medium | Primary purpose | Must support session recovery |
| --- | --- | --- | --- | :-: |
| CLI presentation | Human or one-off script | stdout text / single JSON object | Report the result of this run | No |
| Live event protocol | Runner, SDK, UI | stdout NDJSON | Observe tool calls, messages, and usage in real time | No |
| Session store | The agent itself | JSONL, SQLite, multi-file directory | continue / resume / fork / compaction | Yes |
| Benchmark trajectory | Harbor, offline analyzer | JSONL, ATIF, etc. | Count steps, tokens, and costs, and attribute failures | Usually no |
| Diagnostics / telemetry | Developer, observability platform | stderr, logs, spans, trace files | Troubleshooting, performance analysis, operational monitoring | No |

This distinction explains an apparently contradictory fact: **an agent can emit live events to stdout with `stream-json` while simultaneously writing a separate, more complete and recoverable session into its own data directory.** The former is the protocol for this subprocess invocation; the latter is product state.

The recommended internal structure is one event source feeding multiple projectors:

```text
                         ┌─ text renderer ───────────────> stdout
agent loop ─> canonical ├─ final JSON reducer ──────────> stdout
              events     ├─ NDJSON event serializer ────> stdout
                         ├─ trajectory writer ───────────> requested file
                         ├─ session recorder ────────────> session store
                         └─ diagnostics / telemetry ─────> stderr / exporter
```

`--output-format` selects only one of the first three stdout projectors; `--trajectory` controls the fourth sink; if resume support is added later, the fifth session recorder should be designed separately. This prevents one parameter from simultaneously carrying three responsibilities: format, enablement, and path.

---

## 3. Interface Overview Across Five Projects

The table below compares **actual wire protocols**, not each project's chosen terminology.

| Project | Human-readable text | Single aggregate JSON object | JSONL event stream | Partial / delta capability | Explicit terminal event | Persistent session |
| --- | --- | --- | --- | --- | --- | --- |
| Pi | Print mode | — | `--mode json` | `message_update` deltas | `agent_settled`; `agent_end` ends only one low-level run | JSONL by default; supports continue/resume/fork/`--no-session` |
| Claude Code | `--output-format text` | `--output-format json` | `--output-format stream-json` | Add `--include-partial-messages` | `result` | JSONL by default; supports continue/resume/fork/`--no-session-persistence` |
| Codex | `codex exec` default | — | `codex exec --json` | No public token-delta contract | `turn.completed` / `turn.failed`; interrupt is an exception | Rollout JSONL by default; supports `--ephemeral`, resume, and fork |
| OpenCode | `opencode run --format default`, possibly with multiple completed text segments | `opencode export` is a separate command, not a run output mode | `opencode run --format json` | No; only coarser completion events | None; relies on EOF + exit code | SQLite + internal event table; supports continue/session/fork |
| Grok Build | `--output-format plain`, writes text chunks as they are generated | `--output-format json` | `streaming-json`; also has a Messages-compatible stream | The native stream emits text/thought chunks by default; only the compatibility stream adds a partial flag, and some deltas remain coarse-grained | Native stream: `end` on success and `error` on failure; compatibility stream: `result` | Multi-file JSONL session by default; supports continue/resume/fork |

Three common patterns are visible in this table:

- Human-facing modes tend to put only the final answer on stdout and send progress and diagnostics to stderr.
- Real-time machine-facing modes almost universally use “one object per line” JSONL rather than a long-lived JSON array.
- Sessions are usually persisted automatically and managed by session ID; none of these projects treats `--output-format` as a session switch.

There are also two differences that cannot be inferred from “industry convention”:

- `json` may mean either a single object or JSONL. Claude/Grok use the former; Pi/Codex/OpenCode use the latter.
- “Streaming” may mean only **emitting events immediately as they occur**, or may additionally include text/thinking/tool-argument deltas at different granularities. Claude uses an extra flag to enable raw partials; Grok's native stream already includes text/thought chunks by default, while its extra flag changes only the framing of the Messages-compatible stream. This shows that “streaming” and “token-level” are not the same promise.

---

## 4. Designs by Project

### 4.1 Pi: `json` Is an Event Stream, While the Session Is a Separate Tree-Shaped JSONL

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

Pi's session is a separate append-only JSONL file. It has a session header plus message, model-change, compaction, branch, and other entries carrying `id` / `parentId`; its history is therefore fundamentally a tree rather than a verbatim copy of stdout events. Switching branches merely moves the current leaf and does not delete the other branch. Compaction changes the active context sent to the model without erasing the original history.

**Lessons worth adopting:**

- Deltas and final snapshots have clearly separated responsibilities in the stream.
- Session entries have persistent IDs and parents; ephemeral stdout event IDs do not carry recovery responsibilities.
- The stdout guard and backpressure handling are appropriate for any JSONL CLI.
- One drawback is naming the JSONL mode `json`: callers must read the documentation to know it is not a single object.

Source entry points: [JSON event stream documentation](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md), [RPC event reference](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md), [print mode](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/src/modes/print-mode.ts), and [session format](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/session-format.md).

### 4.2 Claude Code: The Clearest Separation of text, json, and stream-json

Claude Code's public definitions most directly answer this document's naming question:

| Format | Wire protocol |
| --- | --- |
| `text` | Emit the final plain text after completion |
| `json` | Emit **one** result object after completion, containing result, session ID, usage/cost, and other metadata |
| `stream-json` | Emit SDK messages/events line by line during the run, as NDJSON |

By default, `stream-json` means “emit a message or event as soon as it is produced”; it does not automatically mean “emit every token.” Only when `--include-partial-messages` is also specified do raw `stream_event` records appear, containing text, thinking, or tool-input deltas. This separation is worth preserving: many benchmarks need only tool starts/ends, final messages, and usage, and do not need the volume or compatibility cost of token-level events.

It also has two concepts that are easily confused with trajectory but are in fact entirely different:

- `--input-format stream-json` controls stdin; it is not inferred implicitly from the output format.
- `--replay-user-messages` is input-confirmation echoing for duplex clients, not a replay of an old session trajectory.

Claude Code saves sessions by default under `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. Continue, resume, and fork operate on this persistent state; stdout's text/json/stream-json setting affects only how the current invocation reports to its parent process. `--no-session-persistence` is also a separate switch.

The local unofficial snapshot shows transcript entries with parent UUIDs, and stores the full contents of large tool results separately on disk while leaving a preview and path in the message. This further demonstrates that a session is a recoverable directed history, not a stdout event log. It also shows that both sessions and streams may contain complete tool arguments, results, and hook stdout/stderr, and must be treated as sensitive data.

**Lessons worth adopting:**

- The three output names map one-to-one to wire protocols, minimizing ambiguity.
- Partial deltas are a separate capability rather than being inseparably bound to the name `stream-json`.
- The terminal `result` aggregates status, final answer, session ID, turn, and usage/cost, so consumers do not need to scan the entire stream to calculate the final result.
- Session persistence is fully orthogonal to stdout representation.

Authoritative contracts: [CLI reference](https://code.claude.com/docs/en/cli-usage), [headless mode](https://code.claude.com/docs/en/headless), [sessions](https://code.claude.com/docs/en/sessions), and [custom session storage](https://code.claude.com/docs/en/agent-sdk/session-storage).

### 4.3 Codex: Default Text, `--json` JSONL, and Automatically Persisted Rollouts

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

Ordinary sessions are written automatically to:

```text
$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread-id>.jsonl
```

Each line's outer envelope carries timestamp, ordinal, type, and payload, and every line is flushed after writing. Resume continues appending to the original rollout; fork creates a new thread ID and materializes the inherited history into a new rollout. The persistence policy retains messages, reasoning, tool calls/outputs, and other data needed for recovery, but filters many transient deltas, begin events, warnings, and UI events. A rollout is therefore not a mirror of stdout JSONL either.

Codex further distinguishes a deeper, opt-in `rollout-trace`: it may record prompts, responses, tool I/O, and terminal output for local troubleshooting. It is not used for resume and is not a stable CLI trajectory interface. Beyond that there is OpenTelemetry. These three similarly named concepts have entirely different purposes.

**Lessons worth adopting:**

- The default mode strictly enforces “results on stdout, diagnostics on stderr.”
- `--output-last-message` demonstrates that an “additional artifact sink” need not change the main output format.
- Rollouts use ordinals, flush line by line, and can repair a torn tail that lacks a final newline.
- JSONL is a public integration surface actually consumed by the SDK, but the schema has no version number, so consumers must still tolerate unknown events, item types, and newly added fields.

Source entry points: [exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs), [stdout contract](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/lib.rs), [exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs), and [rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs).

### 4.4 OpenCode: run's `json` Is Coarse-Grained JSONL, While Sessions Live in SQLite

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

OpenCode's persistence layer differs even more from its CLI stream. Sessions, messages, parts, and internal durable events/projections primarily live in a global SQLite database; `--continue`, `--session`, and `--fork` determine which session is loaded or copied. `opencode export [sessionID]` is a separate command: it writes a materialized session snapshot as one pretty-printed JSON object to stdout, which the user can then redirect with the Shell. It cannot be treated as a final-object mode for `run --format json`.

Large tool outputs have their previews truncated while the full contents are stored in tool-output files under the data directory. Streams, sessions, and exports cannot by default be regarded as having undergone complete secret redaction; `export --sanitize` performs only limited sanitization.

**Lessons worth adopting:**

- A CLI stream can project only semantic events useful to integrations instead of exposing every internal event.
- Session storage can be implemented with SQLite while the wire protocol remains JSONL.
- The counterexample is that terminal footers and schema versions are cheap, yet substantially reduce the cost of inferring runner state.

Source entry points: [run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts), [session tables](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/core/src/session/sql.ts), and [export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts).

### 4.5 Grok Build: The Most Complete Output Matrix, Plus Two Separate Session Logs

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
- **Schema axis:** the agent's own semantic events versus a wire format compatible with an external ecosystem.

It also demonstrates the cost of a compatibility layer: the same internal event must maintain two public projections, some internal states cannot be mapped losslessly, and partial framing, usage, errors, and terminal results must each be defined independently. nanoPyCodeAgent does not need to duplicate this complexity before it has a concrete consumer.

Grok stores sessions by default under `~/.grok/sessions/<encoded-cwd>/<session-id>/`, distinguishing at least:

- `updates.jsonl`: the authoritative session updates for restoring the UI/conversation.
- `chat_history.jsonl`: the history sent to the model, not the session source of truth.
- Other state for summaries, plans, rewinds, signals, feedback, compaction, subagents, and more.

The JSONL writer uses owner-only directories, append, and torn-tail repair. Continue/resume/fork operate on this session; output format remains only a stdout selection for the current headless invocation.

Grok's native `json` / `streaming-json` formats have another rule for usage/cost worth adopting: when the server has not reported the full cost, cost is omitted or marked incomplete rather than writing a missing value as 0. The Messages-compatible stream is constrained by its target schema, so some unknown values still fall back to 0, with the caveat explicitly documented. For nanoPyCodeAgent's own controllable native benchmark protocol, “unknown” and “free” must be separate states.

**Lessons worth adopting:**

- Aggregate JSON and a native event stream coexist, serving simple scripts and real-time runners respectively.
- Graceful termination has an explicit terminal record: `end` for native success, `error` for native failure, and `result` for the compatibility stream.
- Model-input history is separate from product-recovery history, preventing “current context” from being mistaken for “complete trajectory.”
- A compatibility stream should be driven by real integration needs rather than built from the outset.

Source entry points: [headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md), [format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs), [headless writer](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless.rs), and [session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs).

---

## 5. What Exactly Is `stream-json`?

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

### 5.1 How It Differs from Ordinary JSON

| Dimension | `json` | `stream-json` |
| --- | --- | --- |
| Document boundary | All of stdout is one JSON value | Every non-empty line is one JSON value |
| First parseable point | Usually when the run ends | When the first event is produced |
| Memory | Producer/consumer often must aggregate the final result | Can process line by line with approximately constant space |
| Intermediate state | Usually none | Can include tool, message, usage, error, and other events |
| Artifact after interruption | The entire document may be invalid or may never have been written | Earlier complete lines remain parseable, but the exit code must be consulted to identify abnormal termination |
| Best suited for | Shell scripts and CI reading one result | Runners, real-time UIs, Harbor adapters, and observation of long-running tasks |

It is also commonly called **NDJSON** or **JSON Lines / JSONL**. The recommendation here is to use `stream-json` as the CLI enum name and explicitly state in the documentation that “the wire format is NDJSON,” avoiding the misconception that `jsonl` is only appropriate for files.

### 5.2 What It Does Not Automatically Promise

`stream-json` does not automatically imply:

- Token-level output; events may be emitted only for complete messages or tool stages.
- That input is also JSONL; input should be controlled by a separate `--input-format`.
- Automatic saving to a file; the parent process or Shell decides where stdout goes.
- Resume support; recovery requires stable session IDs, persistent entry IDs, context reconstruction, and a compatibility policy.
- A complete audit log; the public stream may intentionally omit prompts, raw provider payloads, secrets, and oversized tool outputs.
- That concatenating all lines yields a valid JSON array. They are simply a sequence of valid JSON values.

If token-level deltas are needed later, the recommendation is to add `--include-partial-messages` as Claude does. Grok likewise demonstrates that native chunks and compatibility framing are two separate layers of capability. Do not burden the first version of `stream-json` with an implicit high-frequency protocol.

---

## 6. What Should `--trajectory PATH` Mean?

Most of the five projects do not have a flag with this exact name because they already have product-level session stores by default: Pi, Claude, Codex, and Grok automatically save JSONL, while OpenCode automatically saves SQLite. Users continue/resume/fork by session ID instead of specifying a trajectory file for each run.

nanoPyCodeAgent does not currently have such a session system. Under that premise, the recommendation is:

```text
--trajectory PATH
```

It expresses two closely related, non-conflicting things at the same time:

1. **Presence enables:** the trajectory artifact for this run is enabled only when the parameter is present.
2. **Value chooses destination:** `PATH` is the file path for that artifact.

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

The JSONL produced by the second and third commands **need not be identical**: the public stream should be stable, small, and safe, while the trajectory may contain more complete attribution fields and truncation metadata. Both should be projected from the same canonical event model to avoid inconsistent facts.

The path contract should also specify:

- `PATH` denotes a file, not a directory.
- Existing files are not overwritten by default, preventing the silent loss of an expensive run; add explicit overwrite semantics separately if needed.
- The file is created as readable and writable by the current user, with target permissions of `0600` on Unix.
- Every record is flushed after writing so a complete prefix remains after a timeout or kill.
- Readers should tolerate a final incomplete line left by a crash, but must not silently ignore a malformed line in the middle.
- `--trajectory -` should not be allowed, because it would make the trajectory compete with the selected stdout formatter for the same protocol channel.

If sessions become **automatically persisted by default** in the future, the semantics should be separated again: `--no-session-persistence` controls whether to save, `--session`/`--resume` control identity, and `--session-path` should be introduced only if overriding the default location is genuinely supported. Do not silently promote today's debug trajectory into tomorrow's resume format.

---

## 7. Recommended Contract for nanoPyCodeAgent

### 7.1 CLI

The recommendation is to expand the original two formats to three:

```text
nanoPyCodeAgent [-p PROMPT | --prompt-file PATH | stdin]
                [--max-turns N]
                [--output-format text|json|stream-json]
                [--trajectory PATH]
```

| Option | stdout contract | Typical consumer |
| --- | --- | --- |
| `text` (default) | Final assistant text only; an empty result may produce empty stdout | Humans and the simplest benchmark runners |
| `json` | Exactly one result object after run initialization; preflight failure may leave stdout empty; no interspersed logs | Shell, CI, one-off scripts |
| `stream-json` | One event per line; graceful termination ends with a terminal event, otherwise EOF + nonzero exit/signal denotes an aborted stream | Harbor adapters, SDKs, real-time UIs |
| `--trajectory PATH` | Does not change stdout; separately writes incremental JSONL | Offline attribution, benchmark reports, debugging |

Diagnostics, retry notices, tracebacks, and human-facing progress must all go to stderr. The original API error may still appear on stderr to satisfy Harbor's error-classification requirements; machine-mode stdout must remain parseable at all times.

### 7.2 Single `json` Result Object

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

If `--output-schema PATH` is added in the future, it should constrain the semantic contents of `result` rather than alter the transport envelope above. Codex and Grok both separate “structured model answer” from “CLI output protocol,” which is the correct boundary.

### 7.3 Minimal `stream-json` Event Set

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

### 7.4 Trajectory Contents and Stability

The purpose of a trajectory is to “explain why this run produced this result.” At minimum, it should support reconstruction of:

- The input task and a summary of the run configuration.
- Each turn's model completion message or a safely filtered response.
- Tool names, arguments, results, errors, and durations.
- Stop reason, turns, usage/cost, and completeness markers.
- The occurrence of compaction/truncation and the size of omitted contents.
- Final status and result.

The first version should, however, be explicitly labeled a **diagnostic/benchmark artifact, not resumable session**. Resume support additionally requires stable parent/entry IDs, branch semantics, model/tool configuration migration, post-compaction context recovery, and long-term schema migration. The session implementations in Pi, Claude, Codex, OpenCode, and Grok all show that this is far more than “read the JSONL back and continue.”

When Harbor requires ATIF, the recommendation is to convert the native trajectory into ATIF at the adapter layer instead of making the agent loop depend directly on a benchmark schema. Only if Harbor becomes the sole primary consumer would it be worth considering ATIF directly as the persistent format.

### 7.5 Security and Data Volume

The sessions/streams of all five projects may store or emit user prompts, reasoning, tool arguments, file contents, command output, environment paths, and provider metadata. Some projects sanitize recognizable secrets from commands or truncate large results, but none provides a universal guarantee that all secrets are removed.

The trajectory should therefore be treated as a sensitive file:

- Use owner-only permissions.
- Explicitly warn in the documentation not to upload raw trajectories.
- Redact API keys, Authorization headers, and recognized credentials before writing.
- Represent large outputs with a bounded preview plus size/hash/truncation metadata.
- If full contents spill to disk, use a directory with the same permissions and define a retention period.
- Make the public `stream-json` more conservative by default than the local trajectory.
- Do not disguise “missing/truncated” as an empty string or 0.

---

## 8. Final Recommendation

The final answers to the questions at the beginning of this document are:

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

These definitions follow the clear naming of Claude Code and Grok most closely, while incorporating Pi's delta/final separation, Codex's stdout/stderr boundary and additional artifact sink, OpenCode's semantic projection, and the common design across all projects of separating sessions from public event streams.

---

## 9. Reference Entry Points

- Pi: [usage](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/usage.md), [JSON event stream](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md), [RPC events](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md), [sessions](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/sessions.md)
- Claude Code: [CLI reference](https://code.claude.com/docs/en/cli-usage), [headless mode](https://code.claude.com/docs/en/headless), [sessions](https://code.claude.com/docs/en/sessions), [session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)
- Codex: [exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs), [exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs), [rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs)
- OpenCode: [run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts), [export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts)
- Grok Build: [headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md), [format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs), [session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs)
