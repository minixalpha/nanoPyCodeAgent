# Event Journal Implementation Protocol v4

> Generated from the Chinese source
> [`../zh-CN/event-journal-protocol-v4.md`](../zh-CN/event-journal-protocol-v4.md).
> Do not edit by hand.

The current writer emits `schema_version = 4` for all runs. Readers and the
ATIF projector continue to accept v1, v2, and v3. Public trajectories remain
ATIF-v1.7. All contracts from [v3](event-journal-protocol-v3.md) still apply
except for the changes below.

## Time budget outcome

`run.completed.payload.outcome` adds `time_budget_exhausted`: the core observed
an exhausted wall-clock budget before starting another model or tool call.
The meanings of `completed`, `max_turns_exhausted`, and `response_truncated`
remain unchanged.

A headless run with a time budget computes its deadline using a monotonic
clock. It checks before each model attempt and before executing every tool
in a reply. After one tool consumes the remaining budget, subsequent tools
do not start. An in-flight model or tool call is not interrupted and may
outlast the deadline. Existing precedence for response truncation and the
turn budget is unchanged; a complete final reply needing no further work
can still end normally.

The optional `run.started.time_budget_seconds` field records the configured
positive integer number of seconds, or null when no budget is configured.
Older journals may omit this field. ATIF preserves it in
`agent.extra.time_budget_seconds`.

Budget exhaustion finalizes normally with `run.completed` and headless exit
code `0`; cost reconciliation and trajectory writing still run. ATIF records
`extra.terminal.status = "completed"` and
`extra.terminal.outcome = "time_budget_exhausted"`. Consumers must inspect
the outcome rather than infer task completion from status alone.

`model.completed` retains all tools requested by the reply. Only tools that
actually execute have `tool.started`, `tool.completed`, and corresponding
ATIF observations. Tools skipped because of the deadline do not produce
fabricated execution events or results.

## Injected model input

The new Native Event `input.injected` records runtime text appended to a
user-role message, separately from the original `user.message`. Its required
payload fields are:

| Field | Type | Meaning |
| --- | --- | --- |
| `model_call_id` | nonempty string | The upcoming model attempt that will use this input, matching the immediately following `model.started`. |
| `content` | string | The complete text appended this time, not a copy of the whole conversation or tool results. |
| `reason` | nonempty string | Reason for injection; time budget reminders use `time_budget`. |
| `source_timestamp` | RFC 3339 UTC or null | Time of injection. |

With a time budget configured, every model attempt, including retries, appends
a reminder to the most recent user message and records this event before
`model.started`. The first reminder follows the task text, subsequent reminders
follow tool results, and retries append to the same message. The system prompt
stays unchanged. Each addition is recorded separately, including the final
warning to stop investigating and write the output file. Original user input
and tool results are not rewritten in the Journal.

ATIF creates a `source = "user"` step for each `input.injected` in Journal
order, with the reminder text in `message`. Here, user denotes the role in the
model request; `extra.injected = true` identifies runtime-generated input.
`extra.model_call_id` and `extra.reason` preserve correlation and purpose. The
step precedes the corresponding model attempt, is not merged into tool
observations, and does not add to `llm_call_count`.

`content` follows the Journal string persistence limit. When truncated, its
metadata is projected into `extra.journal_truncation`. Correlation identifiers
and `reason` are exempt from string truncation.

## Compatibility and validation

Outcomes and event types are closed enums; new values require a schema
increment. v1/v2/v3 records containing `time_budget_exhausted` or
`input.injected` must be rejected, and old readers reject v4. Historical
journals are not rewritten. Existing version boundaries remain:
`response_truncated` is valid from v2 onward, and `model.failed` from v3 onward.

- [`test_time_budget.py`](../../../tests/test_time_budget.py) covers deadline
  checks before each tool and Journal/ATIF persistence of initial reminders,
  reminders after tool results, and the final warning.
- [`test_truncation.py`](../../../tests/test_truncation.py) covers outcome
  version boundaries; [`test_event_journal.py`](../../../tests/test_event_journal.py)
  covers the injected event's version boundary.
- [Harbor compatibility tests](../../../benchmarks/harbor/tests/test_atif_compatibility.py)
  validate the v4 projection, including reminders and the budget outcome,
  against the pinned official ATIF validator.
