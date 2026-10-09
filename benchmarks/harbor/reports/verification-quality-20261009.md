# Verification quality and long-command guidance comparison

**Status: running; 6 of 24 trials have finished.** This report is incomplete and
makes no capability or efficiency improvement claim. The first verification
candidate pipeline trial scored zero. The matching control also has raw reward
zero, but its verifier failed during dependency download without starting the
tests. That raw reward is retained and classified as a verifier dependency error,
excluded from capability-score comparisons. Both operations pipeline trials also
scored zero after their tests executed. The second control also encountered a
verifier dependency error. The second verification candidate passed all four
official tests. All six pipeline trials have finished. Neither pipeline control
has a valid capability score, so no fresh paired score comparison is available
for this task. Scheduler trials are now running.

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

Both operations-arm pipeline trials have also finished. Each still incurred
one 120-second tool timeout by placing `cd ... &&`
outside the redirected background group. One recovered too late to execute its
real-model harness and disclosed the limitation. The other passed a single-rank
comparison of all 39 parameter gradients and completed a two-rank run. Its
two-rank analysis selected nonzero gradients as owned parameters, which could
hide an expected gradient that is absent. Its hook harness summed backward
captures instead of preserving microbatch identity and failed with a shape
mismatch. The final response disclosed that unresolved activation-check gap.
These are partial verification results, not evidence that every requirement was
checked. Neither operations trajectory showed external task-answer exposure.

Both operations verifiers timed out once during dependency download, then
completed actual tests on the second attempt with two failures and two passes.
Both failed single-rank `lm_head.bwd` and two-rank `model.layers.1.bwd`
microbatch comparisons. The maximum differences were 0.1428563/0.0421933 in
repeat 1 and 0.0416673/0.0146767 in repeat 2. Successful parameter-gradient
self-checks in repeat 2 therefore did not establish the required per-microbatch
activation agreement. No patch-and-rerun causal attribution has been performed.

The second control passed real single-/two-rank checks of per-layer microbatch
activations, owned parameter gradients, and loss. It fixed test collection/index
errors while retaining the selected microbatches, and excluded non-owned
parameters using rank/layer ownership. A check on Transformers 4.38.2 then found
an implementation compatibility bug. After fixing it, the agent reran 4.38.2 and
4.46.3; its earlier 4.53.3 result was not refreshed despite the final three-version
summary. Its official verifier could not fetch the pytest package index and
never started tests; the native zero is classified as another verifier error.

The second verification candidate ran real checks and fixed broadcast result
handling, incompatible model inputs, and backward microbatch ordering. It still
failed two-rank tied embedding/head gradient checks, then changed the harness to
untied weights and obtained passing numerical flags. That leaves the tied case
unresolved. Its harness also skips unobserved layers without an independent
partition assertion. The final model call exhausted the 720-second work budget,
so there was no final summary and its cost/usage accounting is partial. These
positive repair actions and remaining evidence gaps are both retained.
The official verifier subsequently passed all four tests on its first attempt.
That pass does not resolve the broader tied-weight self-test failure or missing
final disclosure.

Pipeline interpretation also needs a contract caveat. After all six pipeline
agent outputs were fixed, the known diagnostic verifier was reviewed again: it
compares hook records in call order against reference microbatches processed in
input order. The public AFAB wording does not specify backward microbatch order.
A self-check that aligns gradients by microbatch identity can therefore validate
numerical behavior while differing from the verifier's ordering constraint.
This does not make an incomplete self-check sufficient, and no counterfactual
official rerun was performed. Hidden tests for the two new tasks remain unread.

## Local and CI validation

Core tests: **351 passed, 4 skipped**. Harbor workflow tests: **99 passed**.
The eight orchestration tests passed again after tightening the preflight gate
to require every planned installation result. Draft PR #48 passed the Python
3.13, Python 3.14, and Harbor workflow CI checks. Research notes are unchanged in
both languages.
