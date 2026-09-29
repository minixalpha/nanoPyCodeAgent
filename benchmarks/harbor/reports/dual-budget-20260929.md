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
budget. Bash interruptions terminate the command's process group and, on Linux,
other members of its session. Cleanup closes output pipes instead of waiting
for detached descendants to close them; reaping the direct child is limited to
one second. Normal exits preserve background services. Stream retries must fit inside the remaining
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
against the repeated control before proceeding: a per-task mean cost or
duration above 1.5 times its control mean holds the pipeline for investigation.
Incomplete cost/provider receipts also hold the pipeline. Do not select the
best run. If the gate passes, run the
original pinned pilot20 selection once with the same model and provider, 100
replies, and task-specific budgets of native timeout minus 180 seconds. Its
supervisor interrupts at native timeout minus 120 seconds and retains 120
seconds of grace. Historical
pilot20 used another model/routing configuration and is not a controlled
estimate of this implementation's effect.

These small repeated samples can reveal regressions but do not establish a
general optimal default. Provider load, cache state, and sampling remain
sources of variation despite a fixed endpoint.

## Revision during live trials

The original treatment (`847cc9895`) exposed a subprocess cleanup defect during
its second Caffe trial. The model invoked `timeout 600 wget ...`; GNU `timeout`
created another process group. Killing the shell's group at 120 seconds left
that child holding the output pipes, so the subsequent unbounded `communicate()`
waited for it. This observation blocks pilot20 independently of reward.

The repair kills other members of the command's session on Linux, closes the
pipe readers without draining them, and bounds direct-child reaping. The first
two treatment repetitions remain preserved as superseded evidence; the third
was cancelled before launch. The three originally planned control repetitions
remain the comparison baseline. All three treatment repetitions will run again
with the repaired, committed wheel and the same provider/configuration. They
will be evaluated together against the same registered gate. This revision
changes the originally alternating execution order; it does not select the
best treatment trials or discard the defect from the report.

## Local validation

The pinned benchmark environment passes 354 tests across the main package and
Harbor adapter. Tests cover early turn-based finalization, stable system
prompts, reminder journaling, stalled streams, real long-running commands,
child-process termination (including GNU `timeout` creating another process
group), bounded cleanup with detached pipe holders, preservation of background services after normal
exit, bounded retries, bounded cost reconciliation, and ATIF compatibility.
