# Event Journal Implementation Protocol v3

> Generated from the Chinese source
> [`../zh-CN/event-journal-protocol-v3.md`](../zh-CN/event-journal-protocol-v3.md).
> Do not edit by hand.

v3 uses `schema_version = 3`. The current writer has moved to
[v4](event-journal-protocol-v4.md); this document preserves the v3 protocol.
v3 readers and the ATIF projector continue to accept v1 and v2. Public
trajectories remain ATIF-v1.7. All contracts from
[v2](event-journal-protocol-v2.md) still apply except for the additional event
and projection behavior described here.

## Failed model attempts

`model.failed` terminates an API attempt without claiming a complete message or
complete usage. It has these required payload fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `model_call_id` | nonempty string | The corresponding `model.started` identifier. |
| `error_type` | nonempty string | Original exception class name. |
| `message` | string | Original exception message. |
| `generation_id` | nonempty string or null | Provider header captured when the stream opens. |
| `duration_ms` | nonnegative number | Attempt duration including stream consumption. |
| `will_retry` | boolean | Whether the agent scheduled another attempt. |
| `retry_delay_seconds` | nonnegative number | Scheduled delay; zero when no retry is scheduled. |
| `source_timestamp` | RFC 3339 UTC or null | Event time. |

The event is emitted for caught SDK and transport errors, including final
failures. Unexpected exceptions and user interrupts retain the previous
`model.started` / `run.failed` representation. Each retry gets a new
`model_call_id`; it is not another completed reply and does not consume the
turn budget. Retries retain the last committed conversation and never execute
tools from the interrupted attempt. `will_retry` records intent: cancellation
or a journal failure may prevent the next attempt from starting.

The recovery policy retries only response-body read errors, read timeouts,
and remote protocol errors, with delays of 1 and 2 seconds. No new retry is
scheduled after a 300-second window starting at the first interruption of the
reply. An in-flight request can outlast that scheduling window; SDK timeouts
and an external supervisor's deadline remain independent limits. Failures
before the stream opens retain SDK retries without another outer retry layer.

## Projection and costs

Failed attempts become chronological agent steps, containing any visible text
deltas, `llm_call_count = 1`, and `extra.incomplete = true`. Error and retry
details remain in `extra`. They contain no tool calls or observations because
no tools from that response were executed. A later successful retry may end
the run normally without making the earlier attempt complete.

Generation IDs are captured before reading the response body so finalization
can reconcile interrupted generations too. Resolved costs contribute to the
total; unresolved attempts keep cost totals explicitly partial. Missing token
usage remains unknown even when billing is resolved. Legacy incomplete model
starts still project as before.

v1/v2 records containing `model.failed` are rejected. Old readers reject v3
rather than silently dropping failed attempts. Historical journals are not
rewritten.
