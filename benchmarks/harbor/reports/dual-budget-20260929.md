# Dual-budget finalization with a fixed provider

## Implementation

Headless runs receive append-only reminders of their remaining model replies
and, when configured, wall-clock time. The system prompt stays fixed. Either
10 remaining replies (including the next reply) or the existing time reserve
(`max(180 seconds, 15% of the task budget)`) triggers finalization guidance:
save required deliverables, perform necessary checks, then summarize and stop.
The final allowed reply cannot execute tools; the reminder states this limit.
The ordinary CLI and Harbor defaults remain 50 replies and 32768 output tokens.

Configured wall-clock budgets interrupt blocking model streams and tool work
using a POSIX main-thread timer. Socket and bash timeouts also use the remaining
budget. Bash interruptions terminate the command's process group; normal exits
preserve background services. Stream retries must fit inside the remaining
budget. Cost reconciliation has a separate shared 30-second cap, after which
unresolved costs remain pending and the native Journal/ATIF can be finalized.
Callers with an existing real-time alarm, non-main threads, and platforms
without `setitimer` receive an explicit error for time-budgeted runs.

## Registered comparison

- Model: `deepseek/deepseek-v4.1-flash`.
- Provider endpoint: `parasail/fp8`, with both `only` and `order` restricted to
  that endpoint and `allow_fallbacks=false`. Pinning is applied by the experiment
  wrapper to both arms, not through a change to account-wide routing settings.
- Control: the source/wheel used by experiment 3 (`83e5c064d`).
- Treatment: the committed dual-budget implementation in this branch.
- Tasks: the same pinned `caffe-cifar-10` and `mteb-leaderboard` task refs.
- Three attempts per task per arm, in separate preserved jobs, alternating arm
  order across pairs. Two simultaneous trials, 100 replies, 65536 output tokens,
  3420 seconds for task work, no whole-task retries.
- Native Harbor task/setup/verifier timeouts are preserved. The supervisor
  remains at 3480 seconds with 120 seconds of finalization grace.
- Dependencies and cached image digests match experiment 3. No fault injection.
- Verify actual provider receipts for all model requests, not just the routing
  configuration. Preserve incomplete receipts as unknown rather than treating
  missing costs as zero; post-run reconciliation may supplement benchmark
  accounting without modifying the agent's native Journal or trajectory.

The initial provider preflight returned a tool call and a generation receipt
identifying Parasail. OpenRouter documents `provider` on its
[Messages endpoint](https://openrouter.ai/docs/api/api-reference/anthropic-messages/create-messages)
and endpoint-specific restrictions in its
[routing reference](https://openrouter.ai/docs/guides/routing/provider-selection).

## Gate for pilot20

The treatment must score reward 1 and end as native `completed` on all six
targeted trials, with no supervisor deadline, forced kill, or reconstructed
trajectory. Provider auditing must succeed. Compare per-task cost and duration
against the repeated control before proceeding; investigate a material
regression rather than selecting the best run. If the gate passes, run the
original pinned pilot20 selection once with the same model and provider, 100
replies, and task-specific budgets inside each native timeout. Historical
pilot20 used another model/routing configuration and is not a controlled
estimate of this implementation's effect.

These small repeated samples can reveal regressions but do not establish a
general optimal default. Provider load, cache state, and sampling remain
sources of variation despite a fixed endpoint.

## Local validation before live trials

The pinned benchmark environment passes 351 tests across the main package and
Harbor adapter. Tests cover early turn-based finalization, stable system
prompts, reminder journaling, stalled streams, real long-running commands,
child-process termination, preservation of background services after normal
exit, bounded retries, bounded cost reconciliation, and ATIF compatibility.
