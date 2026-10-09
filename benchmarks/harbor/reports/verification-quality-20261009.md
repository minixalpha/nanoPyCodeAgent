# Verification quality and long-command guidance comparison

**Status: running; 2 of 24 trials have finished.** This report is incomplete and
makes no capability or efficiency improvement claim. The first verification
candidate pipeline trial scored zero. The matching control also has raw reward
zero, but its verifier failed during dependency download without starting the
tests. That raw reward is retained and classified as a verifier dependency error,
excluded from capability-score comparisons. The operations arm is now running.

The [registered plan](../configs/verification-quality-20261009/experiment.json)
and [reproduction instructions](../configs/verification-quality-20261009/README.md)
freeze three variants, four task revisions, and two repeats per task and arm.
The [structured results](../results/verification-quality-20261009.json) retain
pending outcomes separately from completed scores. The [trajectory audit](../results/verification-quality-audit-20261009.json)
is manual and unblinded; its current entries cover only completed agent runs.

## Frozen variants

| Arm | Source | Prompt words | Change |
| --- | --- | ---: | --- |
| Control | `2eb99b608dfb39464d17d109a4a8f11afda607a9` | 385 | Main with the task-supplied-reference clarification |
| Verification | `3b69d6d` | 482 | Concrete evidence selection, real-entry checks, item coverage, justified test corrections, and final-version evidence review |
| Operations | `ca624b0` | 480 | Explicit Bash limits, redirected background commands, completion status, and intermediate deliverables |

Only `HEADLESS_SYSTEM_PROMPT` differs in the frozen runtime sources. Removing
that assignment produces identical agent ASTs; all other runtime/adapter Python
files are unchanged. The primary branch also contains experiment orchestration,
but every trial is built by the standard runner from its isolated frozen source.

All arms use the official DeepSeek endpoint with `deepseek/deepseek-flash`,
100 replies, and 65,536 output tokens per response. Temperature and reasoning
effort are not explicitly configured. At most two trials run concurrently.
Whole-trial retries are disabled. Only verifier timeouts retry, at most three
attempts with the same agent output and original per-attempt deadline.

## Scope and setup

The diagnostic tasks are `torch-pipeline-parallelism` (720 seconds of model
work) and `llm-inference-batching-scheduler` (1,620 seconds). The two tasks outside
the previous pilot20 tuning cohort are `build-cython-ext` and
`cancel-async-tasks` (720 seconds each). Each task runs twice in each arm.
This is an exploratory subset comparison, not a new twenty-task score.

The experiment designer previously inspected pipeline evaluation code during
post hoc diagnosis. Neither candidate receives a task-specific backward-order
rule, hidden expected answer, function name, or model configuration. Candidate
text was drafted before reading the new tasks' public instructions. Their hidden
tests and solutions remain uninspected until every scheduled output is fixed.

[Install-only evidence](../results/verification-quality-preflight-20261009.json)
records four successful control task installations and one successful wheel
installation for each candidate. All four verifier-dependency profiles are
explicitly `not_configured`; these installation checks do not certify official
verifier dependencies. The original task image IDs are recorded, and both
diagnostic images match the prior pilot. Task files and official scripts remain
unchanged.

## Initial observations, pending the remaining trials

The first control pipeline trajectory exercised a small real Llama model. Its
single-rank check compared all selected microbatch activations and 39 parameter
gradients against a full-batch reference through the model's own forward path.
That check passed. Two-rank checks timed out or produced no completion output;
the final response disclosed this gap. Its network requests retrieved general
Transformers/PyTorch source and packages, with no task-answer retrieval observed.

The first verification-candidate pipeline trajectory saved an implementation and
passed `py_compile`, but could not import Torch. It wrote a numerical harness
without executing it. Two Bash commands hit the 120-second tool limit, including
one with an inner `timeout 300`. The final response explicitly disclosed that
runtime behavior was unverified. Exact-function searches returned authentication
errors, missing endpoints, security challenges, or no answer links; no task-answer
content was observed. These attempts are recorded even without confirmed exposure.

The candidate's official verifier completed with reward zero: the single-rank
case failed a backward-activation comparison (`lm_head.bwd`, maximum difference
approximately 0.5714225), while the two-rank case raised `AttributeError` because
`local_targets[micro]` was `None`. The implementation chose multiplication by the
microbatch count and reverse-order backward processing. This output had no
successful numerical self-check. The failure is retained without a replacement
model run.

The control verifier timed out twice at its original 900-second deadline. Its
third attempt terminated after a network timeout while downloading/extracting
`nvidia-cufft-cu12`. The unchanged task script then wrote reward zero, even though
pytest never started. Harbor reported a scored zero with no exception. The
structured evidence preserves that native status and reward, but records an
analytical `verifier_error` with no valid capability score. No extra verifier
attempt or replacement model run is added.

These two trajectories do not show improved verification coverage from the
expanded verification prompt. They also do not establish a general regression:
the remaining repetitions and tasks have not finished, dependency-download
conditions differed, and the control's raw zero is invalid as capability evidence.

Both operations-arm pipeline agents have also finished; their official verifiers
are pending. Each still incurred one 120-second timeout by placing `cd ... &&`
outside the redirected background group. One recovered too late to execute its
real-model harness and disclosed the limitation. The other passed a single-rank
comparison of all 39 parameter gradients and completed a two-rank run. Its
two-rank analysis selected nonzero gradients as owned parameters, which could
hide an expected gradient that is absent. Its hook harness summed backward
captures instead of preserving microbatch identity and failed with a shape
mismatch. The final response disclosed that unresolved activation-check gap.
These are partial verification results, not evidence that every requirement was
checked. Neither operations trajectory showed external task-answer exposure.

## Local and CI validation

Core tests: **351 passed, 4 skipped**. Harbor workflow tests: **99 passed**.
The eight orchestration tests passed again after tightening the preflight gate
to require every planned installation result. Draft PR #48 passed the Python
3.13, Python 3.14, and Harbor workflow CI checks. Research notes are unchanged in
both languages.
