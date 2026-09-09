# Event Journal Implementation Protocol v2

> Generated from the Chinese source
> [`../zh-CN/event-journal-protocol-v2.md`](../zh-CN/event-journal-protocol-v2.md).
> Do not edit by hand.

v2 is implemented and is the internal Journal protocol used by the current
writer, with `schema_version = 2`. This document defines all changes relative
to [v1](event-journal-protocol-v1.md). Envelope, event types, fields, validation,
ordering, persistence, and projection rules not listed here follow v1. Public
trajectories remain ATIF-v1.7.

## Response truncation outcome

`run.completed.payload.outcome` accepts these values:

| Value | Meaning |
| --- | --- |
| `completed` | The model ended its reply; this does not establish verifier success. |
| `max_turns_exhausted` | The final reply still requests tools, but no reply budget remains, so those tools are skipped. |
| `response_truncated` | The model returned `stop_reason="max_tokens"`, reaching its generation length limit, and the run stopped. |

`model.completed` means an API call returned its final message and usage. It
does not guarantee that the model finished its reply. Truncated replies still
produce this event, preserving `stop_reason="max_tokens"`, original content,
tool calls, usage, and available provider identifiers. Normal cost
reconciliation still runs during finalization.

The core recognizes truncation before checking the turn limit or executing
tools. A reply that also spends the last turn therefore records
`response_truncated`. All tools in that reply are skipped: there are no
`tool.started` or `tool.completed` events and no fabricated observations.
Existing text remains on stdout, the truncation diagnostic goes to stderr,
and headless mode exits `0`. The current policy stops without automatically
continuing, retrying, or raising the 8192-token limit.

This is a budget outcome with an explicit reason, represented by
`run.completed` rather than `run.failed`. ATIF's `extra.terminal.status`
remains `completed`, meaning the run finalized normally;
`extra.terminal.outcome = "response_truncated"` carries the specific result.
The corresponding model step has `extra.stop_reason = "max_tokens"`.
Consumers MUST inspect the outcome to identify truncation rather than infer
task completion from status alone.

Interactive mode returns to the input prompt. Request history retains only
the reply's text and an explicit truncation notice, removing unexecuted tool
calls and non-text blocks such as potentially unfinished thinking. This keeps
unmatched tool calls and incomplete signatures out of the next request. The
original model reply is still stored under the Journal persistence rules;
history repair does not rewrite runtime facts or invent tool execution events.

## Compatibility

- v1 has a closed outcome enum. Adding a value requires a schema increment,
  rather than a v1 optional extension.
- The new writer emits `schema_version = 2` for all runs. The new reader/replay
  implementation and ATIF projector support both v1 and v2. Existing v1
  journals are not rewritten, and historical `completed` outcomes are not
  reclassified retroactively.
- A v1 record containing `response_truncated` is rejected. Old readers
  explicitly reject the v2 schema.
- Other unknown schemas are still rejected. The remaining v1 compatibility
  rules continue to apply.
- The top-level `truncation` field retains its meaning for Journal string
  persistence limits, which are independent of model generation length limits.

## Implementation and validation

- [`agent.py`](../../../src/nanopycodeagent/agent.py): explicit RunOutcome,
  truncation termination, text diagnostics, and interactive history handling.
- [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py): v2 writer,
  v1/v2 replay, and outcome validation.
- [`atif.py`](../../../src/nanopycodeagent/atif.py): projection from both Journal
  versions to ATIF-v1.7.
- [`test_truncation.py`](../../../tests/test_truncation.py): text, thinking,
  empty replies, partial tool JSON, the final turn, costs, trajectories, and
  the next interactive turn.
- [Harbor compatibility tests](../../../benchmarks/harbor/tests/test_atif_compatibility.py):
  the old v1 fixture and new v2 truncated trajectories pass the pinned official
  ATIF validator.
