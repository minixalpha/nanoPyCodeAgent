# Verification quality and long-command guidance comparison

**Completed: 24/24 trials, ending 2026-10-09 18:09:40 UTC.** On the six
common eligible task/repeat cases, control passes **5/6**, verification **6/6**,
and operations **6/6**. Both candidates gain only the first scheduler repeat;
neither regresses on these six cases. All arms pass **4/4** cases on the two
tasks outside prior tuning. This is an exploratory signal, not evidence of a
stable general improvement. Keep the candidate experimental; do not promote it
from these results alone.

The verification prompt produces more observed checks that reject deliberately
incorrect results, but still abandons a failing tied-weight pipeline case. The
operations prompt does not eliminate tool timeouts. These findings favor
improving requirement coverage and evidence tracking, rather than treating a
longer prompt or a passing official score as sufficient verification.

## Evidence and frozen design

The [registered plan](../configs/verification-quality-20261009/experiment.json),
[reproduction instructions](../configs/verification-quality-20261009/README.md),
[structured results](../results/verification-quality-20261009.json),
[24-trial audit](../results/verification-quality-audit-20261009.json), and
[integrity record](../results/verification-quality-integrity-20261009.json)
retain all outcomes, artifact hashes and evidence references. The audit is
manual and unblinded. Local job directories contain the full private traces;
published results contain metadata and reviewed evidence summaries.

This follows the [last pilot20 comparison](headless-p0-guarded-20261007.md), whose
candidate scored 19/20 with pipeline parallelism as its only scored failure.
That earlier result belongs to its frozen 368-word prompt, not the later
385-word reference clarification used as this experiment's control. The earlier
common eligible comparison excludes MTEB due to reference/test exposure. This
four-task experiment is **not a new twenty-task score**.

| Arm | Frozen runtime source | Prompt words | Change |
| --- | --- | ---: | --- |
| Control | `2eb99b608dfb39464d17d109a4a8f11afda607a9` | 385 | Main with task-supplied-reference clarification |
| Verification | `3b69d6d54cec29bbeaa129914419c90a70fb87d7` | 482 | Real-entry checks, item coverage, justified test corrections, negative controls, final-version evidence |
| Operations | `ca624b0c02c5c543dffd3c99efbad031d7658afb` | 480 | Bash deadlines, background redirection, completion status, intermediate deliverables |

Only `HEADLESS_SYSTEM_PROMPT` differs between frozen runtimes. The agent AST
without that assignment is identical; other runtime/adapter Python files are
identical, apart from generated package-version metadata. No finish gate or
runtime verification machinery was added. Each candidate is a bundle of prompt
changes; individual sentences cannot be credited separately.

Each arm runs four tasks twice. Pipeline, Cython and async work budgets are
720 seconds; scheduler is 1,620 seconds. All use `deepseek/deepseek-flash` at the
official DeepSeek endpoint, 100 replies and 65,536 output tokens per request.
Temperature and reasoning effort are unset. Setup has a separate 1,800-second
limit. The queue rotates arms, runs at most two trials concurrently, and waits
for each pair to finish. Repeat indices are not shared random seeds.

There are no replacement model runs or whole-trial retries. Only verifier
timeouts retry, with at most three attempts on the same output and the original
900-second limit (1,800 for scheduler). All jobs use the standard Harbor runner.

## Official outcomes

Cells list repeat 1 / repeat 2. `E (raw 0)` means verifier dependencies failed
before tests started; the native zero remains recorded but is not a capability
failure.

| Task | Cohort | Control | Verification | Operations |
| --- | --- | --- | --- | --- |
| `torch-pipeline-parallelism` | Diagnostic | E (raw 0) / E (raw 0) | Fail / Pass | Fail / Fail |
| `llm-inference-batching-scheduler` | Diagnostic | Fail / Pass | Pass / Pass | Pass / Pass |
| `build-cython-ext` | Outside prior tuning | Pass / Pass | Pass / Pass | Pass / Pass |
| `cancel-async-tasks` | Outside prior tuning | Pass / Pass | Pass / Pass | Pass / Pass |

Across all valid scores, control is 5/6 with two verifier errors, verification
7/8, and operations 6/8. **Those denominators differ.** The common comparison
excludes both pipeline repeats from every arm: control 5/6 versus 6/6 for each
candidate, with five shared passes and one candidate-only pass. No fresh paired
pipeline score is available. Both held-out tasks pass in every arm and repeat.
Cython verifiers each report 11 passed; async verifiers each report 6 passed.

### Why the valid failures occurred

- **Control scheduler, repeat 1:** the official verifier reports one failure and
  five passes. Each output has eight shapes, but their combined union has
  **eleven**, violating the public limit of eight across both files. The agent
  rechecks final files, metrics and input hashes but omits the global union.
  Its final completion claim therefore exceeds its evidence. The other five
  scheduler trials explicitly check the union and pass all six official tests.
- **Verification pipeline, repeat 1:** Torch never becomes available during
  agent work. The agent writes a real-model harness but only executes syntax
  validation, disclosing the gap. Official tests then fail single-rank backward
  activation comparison at `lm_head` (maximum difference about 0.5714225) and
  two-rank execution because `local_targets[micro]` is `None`. Its chosen loss
  scaling and backward order were never numerically validated.
- **Operations pipeline, both repeats:** official tests execute after one
  download-timeout retry per trial; both report two failures and two passes.
  Single-rank `lm_head.bwd` / two-rank `model.layers.1.bwd` differences are about
  0.1428563 / 0.0421933 in repeat 1 and 0.0416673 / 0.0146767 in repeat 2.
  Repeat 1 never runs its numerical harness. Repeat 2 has passing single-rank
  parameter checks, but its microbatch-hook comparison fails and its two-rank
  parameter selection can omit missing gradients. The final discloses the gaps.

These are observed failure locations and verification omissions, not uniquely
proven causal decompositions. No counterfactual patch-and-rerun was performed.

### Why the two control pipeline zeros are excluded

Repeat 1 times out twice at 900 seconds. Attempt 3 returns after a network
failure downloading/extracting `nvidia-cufft-cu12`; the unchanged test script
writes zero although pytest never starts. Repeat 2 cannot fetch the pytest
package index and also never starts tests. That failure is not a verifier
timeout, so it receives no retry. Harbor reports native scored zeros without
exceptions; the analytical classification is `verifier_error` for both.

[Preflight evidence](../results/verification-quality-preflight-20261009.json)
records six successful agent installations before model work. All selected
verifier dependency profiles remain **`not_configured`**. These installation
checks did not certify verifier dependencies. No extra attempts were added to
repair these comparison gaps.

## What changed in verification behavior

### Useful evidence from the verification prompt

Five of eight verification trajectories show a deliberate negative control,
versus none observed in the other arms. Their strength differs:

| Trial | Observed discrimination | Limit of the evidence |
| --- | --- | --- |
| Scheduler repeat 1 | Provided baseline fails three metric thresholds in both buckets | Cost/threshold logic only; not the complete structural checker despite the final wording |
| Scheduler repeat 2 | Same validator rejects four malformed plan copies | Selected coverage/alignment/ID mutations; not every global constraint |
| Async repeat 1 | Same suites reject naive gather and cancel-without-wait runners | Selected cancellation and SIGINT entry points |
| Async repeat 2 | Same real-SIGINT check rejects double-cancel cleanup | One deliberately invalid runner |
| Cython repeat 2 | Numerical comparison rejects a perturbed contribution matrix | Printed boolean from a local numeric check; not a faulty extension build |

The async verification runs first expose actual interrupted cleanup, repair the
implementation, and rerun functional, cancellation and subprocess signal checks
on final files. This is concrete evidence of useful verification work, even
though control and operations also pass the official async tests.

### Remaining gaps, including official passes

**Pipeline verification repeat 2 passes all four official tests but does not
establish all its own claims.** Real-model checks identify broadcast-result and
input-argument bugs, which the agent repairs. It then fails tied embedding/head
parameter checks on two ranks and changes the harness to untied weights without
resolving the tied case. It skips unobserved layers without an independent
partition assertion. An intermediate claim of parameter agreement contradicts
observed output. The final model call exhausts the work budget, leaving no final
summary or disclosure. A zero count of unsupported *final* claims in this arm
must not be interpreted as flawless reporting.

**Operations Cython repeat 2 passes the official verifier but overstates its
self-check.** Its last numerical probe prints `False` for the no-basepoint
comparison and `True` for basepoint. The reference applies the basepoint formula
to both; the agent neither fixes and reruns that oracle nor discloses the
mismatch in its final agreement summary. The error is in the evidence, not a
proven failure of the installed extension. Operations repeat 1 discloses a
broader smoke-test failure, but calls the process still running after a recorded
exit status of 1.

**Operations async repeat 1** verifies direct `asyncio.run` plus real SIGINT and
awaited cleanup, but an outer-gather case still interrupts cleanup. The final
discloses the limitation; its assertion that every coroutine runner shares it
is not established by these traces.

**Control pipeline repeat 2** has strong small real-model checks of activations,
owned parameters and loss. After a compatibility fix it repeats two Transformers
versions, but not the third version included in its final summary. That is one
observed stale verification claim. Cython control repeat 2 removes an invented
figure-eight constant after a mismatch while retaining the Python comparison;
verification repeat 2 broadens a similar constant set. Their remaining checks
are useful, but neither change establishes a case-specific independent constant.

All Cython arms execute the required README example, confirm real compiled
modules in system site-packages with NumPy 2.3.0, and pass the 18-test public
suite using only the two authorized file exclusions. No edits to those public
test assertions were observed. Many probes use `tail`/`grep` without `pipefail`:
we credit visible test results and assertions, not shell exit status alone.

### Pipeline contract caveat

After all six pipeline outputs froze, the known diagnostic verifier was reviewed
again. It zips hook records in call order against reference microbatches in input
order. Public AFAB wording does not specify backward microbatch order. A
self-check that aligns by microbatch identity can validate numerical values while
violating that ordering constraint. This caveat does not make partial self-tests
sufficient, nor establish that order alone explains every failure. No verifier
or task file was modified.

## Cost and execution time

Agent seconds are Harbor execution intervals including tools and finalization,
excluding setup, verifier and queue time. Costs are token-based estimates, not
provider invoices. `>=` marks a known lower bound due to incomplete accounting.

| All eight trials per arm | Control | Verification | Operations |
| --- | ---: | ---: | ---: |
| Estimated USD | >= 0.633712 | >= 0.750448 | 0.598339 |
| Agent seconds | 3,777.7 | 4,124.5 | 3,809.1 |
| Model attempts | 311 | 334 | 272 |
| Incomplete model attempts / accounting trials | 1 | 2 | 0 |
| Bash tool timeouts | 1 | 2 | 3 |
| Truncated responses | 0 | 0 | 0 |

| Six common eligible cases per arm | Control | Verification | Operations |
| --- | ---: | ---: | ---: |
| Passes | 5/6 | 6/6 | 6/6 |
| Estimated USD | >= 0.478366 | >= 0.585636 | 0.462751 |
| Agent seconds | 2,519.0 | 2,747.9 | 2,497.8 |
| Model attempts | 258 | 292 | 229 |

Verification uses **9.1% more agent time** on the common cases. Total-cost
percentage differences are not identifiable from the incomplete estimates.
For a descriptive accounting-complete subset of five common cases (exclude
Cython repeat 2 from all arms), costs are $0.411074 control, $0.500304 verification
and $0.395594 operations. This post hoc accounting subset is not a replacement
score cohort.

The three accounting gaps are control Cython repeat 2 and verification Cython
repeat 2 (recovered incomplete network streams), plus verification pipeline
repeat 2 (final-call deadline). Completed retries do not recover missing usage
for the interrupted requests. All other model runs finish with a final response.

The operations arm still has two pipeline background-command timeouts and one
async shell-signal-driver timeout. The pipeline launches leave `cd ... &&`
outside the redirected group, retaining captured pipes; the async trial later
succeeds with a Python subprocess driver. Prompt instructions alone therefore
do not provide reliable process lifecycle management.

## Integrity, limitations and next experiment

Final checks validate all 24 ATIF trajectories, recorded runtime source hashes,
installed wheel hashes, frozen task/config/prompt hashes, and the four original
image IDs. Every verifier obeys the timeout-only retry policy. All 18 non-pipeline
verifier summaries execute tests; there are no native execution exceptions.
The complete audit finds no confirmed external benchmark-answer/hidden-test
exposure. One pipeline trial attempts exact-function searches without obtaining
an answer. Cython verification repeat 1 consults two upstream files in the
explicitly task-supplied public project; this is recorded as an allowed code
reference, not benchmark-answer retrieval.

Pipeline and scheduler are selected diagnostic tasks, and the designer had
previously seen pipeline evaluation code. Candidate prompts contain no hidden
expected answer or task-specific implementation rule. The two new tasks were
selected from catalog names/public requirements; their hidden tests and solutions
were not inspected before outputs froze. Two repeats, two new tasks, an unblinded
manual audit, uncontrolled network/cache/provider variation, and missing valid
pipeline controls prevent a general causal or statistical claim.

The next implementation priorities are:

1. **Map requirements to evidence, including global constraints.** Track each
   high-risk requirement's scope (item, file, cross-file), observed check result,
   and final artifact version. The scheduler failure shows why per-file checks
   cannot establish a cross-file requirement.
2. **Preserve failed cases and verify the checker.** Prefer a small real entry
   point plus an independent oracle. Keep failing cases visible when correcting
   tests; record why an expected value or coverage selection changes. Use a cheap
   invalid output/implementation for critical custom checks. Tied-to-untied
   substitution must remain an unresolved gap.
3. **Tie completion claims to actual results.** Rerun affected checks after final
   edits; distinguish pass, fail, not run and stale evidence. Preserve the exit
   status of the tested process through pipes. Reserve time for a final evidence
   summary rather than expanding unrelated smoke coverage until the deadline.
4. **Provide managed long-command execution.** Return a process handle, pollable
   status, bounded logs and the actual exit code. Evaluate this runtime change
   separately from verification wording; the operations prompt did not solve it.
5. **Make verifier setup reliable before another comparison.** Add reviewed
   task-revision dependency profiles and tests through the standard adapter.
   Keep task images, package sources and official scripts intact, and report
   infrastructure failure separately from task correctness.

These are follow-up directions, not additional changes tested in this run. A new
preregistered comparison should use fresh task/repeat samples and valid shared
controls; retain this run unchanged and report unsuccessful trials alongside
wins.

## Repository validation

The result collector fails closed on incomplete audits, changed evidence hashes,
changed frozen sources, wheel mismatches or invalid verifier retry policies. It
preserves native zeros and partial accounting, and computes common eligible
cases separately from all-trial totals. Harbor regression tests: **105 passed**,
including six new collection tests. The previously tested frozen prompt/runtime
change passed **351 core tests, 4 skipped**. Research notes in both languages are
unchanged. Draft PR #48 retains the experimental status; this report does not
recommend merging the candidate into main.
