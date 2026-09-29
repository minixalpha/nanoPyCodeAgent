# Dual-budget finalization with a fixed provider

The repaired candidate (`380271dfd`) passed all six targeted trials and ended
as native `completed` in all six. The control passed five of six and ended as
native `completed` in four. The registered gate passed. The subsequent pilot20
scored **18/20**, with all 20 runs ending as native `completed`. Caffe accuracy
and PyTorch pipeline numerical correctness failed their independent verifiers;
normal finalization did not imply task success.

The complete configuration, metrics, and all retained trial rows are in the
[public results](../results/tb21-dualbudget-fixed-provider-20260929.json), including
the four superseded treatment trials. Raw evidence remains in the recorded
Git-ignored `jobs/` directories.

## Targeted results

Each row contains all three repetitions of one task and arm. Time covers the
agent process, including post-task cost reconciliation; work time is measured
from the native journal's run start to its last model/tool completion. Costs
include supplementary receipt reconciliation. Native journals and trajectories
retain their original pending cost entries rather than being rewritten.

| Task | Arm | Reward 1 | Native completed | Replies by repetition | Mean work (min) | Mean total (min) | Mean cost (USD) |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| caffe-cifar-10 | Control | 3/3 | 2/3 | 51, 100, 43 | 31.30 | 33.12 | 0.078184 |
| caffe-cifar-10 | Repaired | 3/3 | 3/3 | 51, 72, 59 | 32.76 | 33.27 | 0.057473 |
| mteb-leaderboard | Control | 2/3 | 2/3 | 72, 100, 43 | 19.44 | 21.67 | 0.073795 |
| mteb-leaderboard | Repaired | 3/3 | 3/3 | 71, 91, 59 | 11.48 | 11.99 | 0.083837 |

The six repaired trials cost $0.423931464 versus $0.455935140 for the six
controls (about 7.0% less). Caffe's mean cost fell 26.5%, while mean total time
was essentially unchanged (+0.4%); mean work time increased 4.7%. MTEB's mean
cost rose 13.6%, while mean total time fell 44.7% and work time fell 41.0%.
These are observations from three repetitions per task, not general effect
estimates or proof that any single component caused the differences.

Both control tasks in repetition 2 exhausted 100 replies. Caffe still scored
1, but MTEB scored 0 because the required `result.txt` did not exist. In the
repaired MTEB repetition 2, the turn-91 reminder fired with 47:34 of time still
available; that reply ended the run normally and the task passed. The other
five repaired trials finished before either finalization threshold fired.

All twelve trials have matching pinned task refs, valid native ATIF, and
complete provider/cost audits. Every recorded model POST applied the provider
restriction, and every received generation was attributed to Parasail. One
control connection-establishment timeout was recovered by the SDK before
response headers; it is recorded separately from received generations. No
repaired trial needed a supervisor deadline, forced kill, or reconstructed
trajectory. The longest completed tool call in the repaired cohort was about
120.11 seconds, versus the superseded treatment's observed 600-second cleanup
wait.

The initial treatment's four completed trials all passed and ended normally,
but they remain separate superseded evidence because of the cleanup defect.
Their total cost was $0.278459916. The unstarted third repetition was cancelled;
all three repaired repetitions were run afresh. No best-run selection was used.

## Pilot20 regression

The original pinned 20-task selection ran once, with two concurrent trials,
the same repaired source, model, and fixed provider. Actual native journals
confirm 100 replies, 65536 output tokens, and task-work budgets of each native
agent timeout minus 180 seconds (12, 27, 37, or 57 minutes). Harbor task, setup,
and verifier timeouts were not overridden. Existing verified QEMU bootstrap
packages and the PyTorch model-recovery verifier package cache were reused;
task instructions, image digests, and verifier logic were unchanged. No task
was retried based on its score.

All 20 tasks were scored: 18 passed and two scored zero. All 20 ended as native
`completed`, with valid native ATIF, matching task refs and runtime budgets,
and the expected source version `0.8.1.dev43+g380271dfd`. There were no Harbor
exceptions, supervisor deadlines, forced kills, or reconstructed trajectories.
All 558 model POSTs applied the provider restriction and match 558 Parasail
generation receipts. There were no failed model attempts or connection failures
before response headers. Full reconciled model cost was **$1.123469172**.
Harbor job wall time was 1 hour 55 minutes 52 seconds with two concurrent trials;
this includes setup and verification, but excludes the later host receipt audit.
The longest completed tool call was about 120.19 seconds.

| Task | Reward | Replies | Work (min) | Budget (min) | Cost (USD) |
| --- | ---: | ---: | ---: | ---: | ---: |
| caffe-cifar-10 | 0 | 66 | 54.07 | 57 | 0.091648 |
| circuit-fibsqrt | 1 | 26 | 6.20 | 57 | 0.068076 |
| dna-assembly | 1 | 29 | 7.83 | 27 | 0.134251 |
| kv-store-grpc | 1 | 10 | 4.96 | 12 | 0.004265 |
| llm-inference-batching-scheduler | 1 | 27 | 3.71 | 27 | 0.063599 |
| log-summary-date-ranges | 1 | 7 | 0.26 | 12 | 0.004642 |
| merge-diff-arc-agi-task | 1 | 16 | 0.88 | 12 | 0.016840 |
| model-extraction-relu-logits | 1 | 17 | 1.61 | 12 | 0.020341 |
| mteb-leaderboard | 1 | 49 | 9.59 | 57 | 0.054133 |
| openssl-selfsigned-cert | 1 | 13 | 0.56 | 12 | 0.006882 |
| path-tracing | 1 | 22 | 2.01 | 27 | 0.064753 |
| pypi-server | 1 | 17 | 5.03 | 12 | 0.008618 |
| pytorch-model-recovery | 1 | 10 | 2.73 | 12 | 0.009207 |
| qemu-alpine-ssh | 1 | 43 | 9.30 | 12 | 0.060265 |
| regex-chess | 1 | 55 | 36.41 | 57 | 0.214995 |
| regex-log | 1 | 7 | 1.72 | 12 | 0.030141 |
| schemelike-metacircular-eval | 1 | 37 | 20.70 | 37 | 0.082982 |
| torch-pipeline-parallelism | 0 | 44 | 9.78 | 12 | 0.074019 |
| torch-tensor-parallelism | 1 | 44 | 6.86 | 12 | 0.062337 |
| write-compressor | 1 | 19 | 2.77 | 12 | 0.051477 |

The two failures were task-solution failures with preserved artifacts:

- **Caffe:** five of six verifier tests passed, including source/build checks,
  model/config files, CPU training, and completion of 500 iterations. The
  verifier extracted accuracy 0.37 against a strict requirement greater than
  0.45. The agent separately reported full-test accuracy 0.4395 and explicitly
  acknowledged missing the requirement. These are distinct measurements, both
  below the threshold. Time-based finalization reminders appeared on replies
  64–66, starting with 7:11 remaining; the run ended normally after 66 replies.
  All three targeted repaired Caffe trials had passed, so this additional
  failure also shows that the targeted result is not a guarantee of reliability.
- **PyTorch pipeline:** two of four verifier tests failed numerical comparisons:
  the one-process case differed at `model.norm.fwd` (maximum difference
  5.190534591674805), and the two-process case at `model.layers.1.bwd`
  (0.013752378523349762). The agent reported passing its own checks, but the
  independent verifier rejected the solution. Time reminders appeared at
  replies 43–44, starting with 2:20 remaining, and it ended normally after 44
  replies. The agent's work budget was not exhausted.

QEMU provides a successful time-based finalization example: reminders started
on reply 40 with 2:57 remaining, and it passed after ending on reply 43. The
other 17 pilot tasks finished before the finalization threshold fired. Together
with the targeted MTEB reply-91 case, these runs exercise both reminder triggers.
They do not establish whether a reminder caused an individual correctness result.

For historical context, the tracked September 6 pilot scored 8/20 using
`deepseek-v4-flash-0731`, account routing, 50 replies, and 8192 output tokens.
The local September 21 stream-recovery pilot scored 11/20 (six zeros and three
unscored trials), with 50 replies, 65536 tokens, and agent/setup overrides of
3780/3600 seconds. The new 18/20 run changes model, routing, budgets, and agent
source relative to those pilots, so the score difference cannot be attributed
solely to dual-budget finalization. Only the targeted repeated comparison uses
the fixed-provider control described in this report.

## Decision

Retain the fixed system prompt, appended budget reminders, early finalization
guidance, and bounded model/tool/cost operations. The registered targeted gate
passed and the full pilot preserved native terminal records for every task.
Keep ordinary defaults at 50 replies and 32768 output tokens; 100/65536 remains
this experiment's configuration. The pilot is not an all-pass result, and this
small study does not establish optimal defaults. Further evaluation should
separate task-solution accuracy and verification quality from runtime
finalization, and use matched controls before attributing score changes.

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
one second. Normal exits preserve background services. Stream retries must fit
inside the remaining budget. Cost reconciliation has a separate shared
30-second cap, after which unresolved costs remain pending and the native
Journal/ATIF can be finalized.
Callers with an existing real-time alarm, non-main threads, and platforms
without `setitimer` receive an explicit error for time-budgeted runs.

## Registered comparison

- Model: `deepseek/deepseek-v4.1-flash`.
- Provider endpoint: `parasail/fp8`, with both `only` and `order` restricted to
  that endpoint and `allow_fallbacks=false`. Pinning is applied by the experiment
  wrapper to both arms, not through a change to account-wide routing settings.
- Control: the source/wheel used by experiment 3 (`83e5c064d`).
- Treatment: the repaired dual-budget source/wheel (`380271dfd`).
- Tasks: the same pinned `caffe-cifar-10` and `mteb-leaderboard` task refs.
- Three attempts per task per arm, in separate preserved jobs. The original
  order alternated arms; the revision below records the actual order change.
  Two simultaneous trials, 100 replies, 65536 output tokens, 3420 seconds for
  task work, no whole-task retries.
- Native Harbor task/setup/verifier timeouts are preserved. The supervisor
  remains at 3480 seconds with 120 seconds of finalization grace.
- Dependencies and cached image digests match experiment 3. Temperature and
  reasoning effort were not explicitly set. No fault injection.
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
sources of variation despite a fixed endpoint. External task services and
network conditions also remain variable.

## Revision during live trials

The original treatment (`847cc9895`) exposed a subprocess cleanup defect during
its second Caffe trial. The model invoked `timeout 600 wget ...`; GNU `timeout`
created another process group. Killing the shell's group at 120 seconds left
that child holding the output pipes, so the subsequent unbounded `communicate()`
waited for it. This observation blocked the original pipeline independently of reward.

The repair kills other members of the command's session on Linux, closes the
pipe readers without draining them, and bounds direct-child reaping. The first
two treatment repetitions remain preserved as superseded evidence; the third
was cancelled before launch. The three originally planned control repetitions
remained the comparison baseline. All three treatment repetitions were rerun
with the repaired, committed wheel and the same provider/configuration. They
were evaluated together against the same registered gate. The actual order was
control 1, superseded treatment 1 and 2, control 2 and 3, then repaired treatment
1, 2, and 3. This changed the originally alternating order without selecting
the best treatment trials or discarding the defect from the report.

## Local validation

The pinned benchmark environment passes 354 tests across the main package and
Harbor adapter. Tests cover early turn-based finalization, stable system
prompts, reminder journaling, stalled streams, real long-running commands,
child-process termination (including GNU `timeout` creating another process
group), bounded cleanup with detached pipe holders, preservation of background
services after normal exit, bounded retries, bounded cost reconciliation, and
ATIF compatibility. The PR checks also passed on Python 3.13 and 3.14.
