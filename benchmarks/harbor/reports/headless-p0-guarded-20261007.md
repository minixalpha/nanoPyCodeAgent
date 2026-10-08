# Headless contract-verification prompt: guarded pilot20 comparison

The frozen 368-word candidate scored **19/20**, compared with **18/20**
for contemporaneous main. The MTEB pair is ineligible for an
independent-capability comparison because of confirmed reference/test exposure.
On the common 19 eligible tasks, the candidate passed **18/19** and main
passed **17/19**. Raw scores and all costs remain unchanged. The current
385-word workspace-reference clarification has a separate single-task check below;
the twenty-task result belongs to `03cfd53`, not that later revision.

The observed extra pass comes with **30.3% more estimated model cost** and
**21.6% more summed agent execution time** in the full comparison.

This is an **adaptive exploratory comparison**, with one run per task and arm on
the original pilot20 cohort. Five main-control outcomes were visible before the
information-boundary revision was registered. All twenty controls were retained
without selection, and all twenty guarded-candidate trials were fresh. There are
no held-out tasks or repeat samples. A score difference on this cohort does not
establish a stable or general capability improvement.

The [structured results](../results/tb21-headless-p0-guarded-20261007.json) preserve
every trial, paired outcome, accounting limitation, integrity finding, and artifact
hash. See the [guarded plan](../configs/headless-p0-guarded-20261007/experiment.json)
and [reproduction instructions](../configs/headless-p0-guarded-20261007/README.md).

## Candidate and frozen inputs

The control is main at `6664f7bac9d7f9b26f49e523ac6ee7e4e8a6b9ac`, including the
already-landed once-per-run truncation recovery. The candidate is
`03cfd534ddb86ea507d43cad9776e86c91d53648`. The full twenty-task candidate is
frozen at this revision. A subsequent wording
clarification is tested separately below; it does not inherit this twenty-task
score. The only runtime source change is `HEADLESS_SYSTEM_PROMPT`:

- Identify deliverables, interfaces, and constraints; examples need not describe
  the full contract.
- Inspect relevant inputs and check output meaning through the actual entry
  point, using task-appropriate representative, boundary, and independent checks.
- Diagnose failed checks, repair the cause, and rerun affected checks; keep
  verification proportional to the task and remaining budget.
- Finish with evidence and disclose limitations.
- Use task-provided material and general documentation; do not seek or use a
  task-specific reference solution or hidden evaluation tests unless the task
  explicitly provides or requests them.

The control prompt has 175 whitespace-separated words; the candidate has 368.
The interactive prompt, tools, budget reminders, recovery policy, and adapter are
unchanged. AST comparison is identical after excluding the headless-prompt
assignment, and the other twenty recorded Python files are byte-identical.

| Setting | Value |
| --- | --- |
| Model / endpoint | `deepseek/deepseek-flash` / `https://api.deepseek.com/anthropic` |
| Tasks | Original twenty pinned pilot20 task revisions |
| Reply / output-token limit | 100 / 65,536 per request |
| Work budgets | 720, 1,620, 2,220, and 3,420 seconds; native agent limits minus 180 seconds |
| Setup timeout | 1,800 seconds, separate from agent work |
| Concurrency | One trial per arm, at most two overall; wait for both arms before the next budget group |
| Whole-trial retries | Zero |
| Verifier retries | Only timeouts, at most three attempts on the same agent output, with the original per-attempt limit |
| Control prompt SHA256 | `54da8191adac5a1b717129a6292f2946544ff4113477427018a3445f4a5af1d4` |
| Candidate prompt SHA256 | `dd0880aa94b48e228c4db5d9a6dafe20e7924e4b417ffe015cb3de192df90dd4` |
| Control wheel SHA256 | `f23e090f3b475550cc968f8f2199b4dca7d204d8cb91b1f2c8640235f514191c` |
| Candidate wheel SHA256 | `40d021942924be15b2f823f17e63850a9f280ce6dd612d3190191a745e0027d3` |

All new jobs used `uv run --project benchmarks/harbor python -m harbor_adapter run`.
Each job snapshots its source and installs its recorded wheel. All four wheels
within each arm have the corresponding hash above.

## Preflight and integrity

All twenty control installations passed before model work. The original candidate
also passed QEMU's registered dependency preflight. After adding the information
boundary, a fresh OpenSSL installation smoke check passed for the guarded wheel.
The unchanged registered QEMU profile also runs before each full QEMU model trial.
The other nineteen dependency profiles remain explicitly **`not_configured`**;
installation success does not certify their official verifier dependencies.

Final checks match all **152 task-file hashes** and
**20 Docker image IDs** to the baseline. All eight source/wheel
snapshots match their frozen arm, and every installed trial wheel matches its job
manifest. All forty task checksums and ATIF trajectories validate. Verifier
attempts retain native limits and comply with the timeout-only, three-attempt
policy. These checks establish artifact consistency; the separate reference
audit below identifies task-answer exposure despite unchanged task files.

A Codex server restart interrupted the outer launcher and queue during the guarded
720-second group. The already-running Harbor child survived and completed all
remaining trials. The queue was restored without restarting a model run. The
missing wrapper summary was reconstructed with the repository's own `summarize`
function after the native job finished. That orphan process's exit code is
**unknown**, recorded as `null`; its individual trial results and native job
completion remain available. Later groups used the unchanged standard runner.

## Per-task results

Agent seconds are recorded Harbor agent-execution intervals, including tool work
and finalization, and exclude queue waiting, separate setup, and verification.
Costs are token-based estimates, not provider bills. A dagger (`†`) flags a raw
score obtained after confirmed external task-answer or hidden-test exposure.
`*` denotes incomplete
accounting; an unknown value is not zero.

| Task | Main reward | Candidate reward | Main seconds | Candidate seconds | Main USD | Candidate USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `write-compressor` | 1 | 1 | 545.1 | 494.7 | 0.055753 | 0.137920 |
| `torch-tensor-parallelism` | 1 | 1 | 539.8 | 297.8 | 0.064382 | 0.039400 |
| `schemelike-metacircular-eval` | 1 | 1 | 1417.6 | 536.9 | 0.146158 | 0.111429 |
| `kv-store-grpc` | 1 | 1 | 55.5 | 196.2 | 0.003459 | 0.015531 |
| `pypi-server` | 1 | 1 | 237.5 | 102.6 | 0.016673 | 0.013724 |
| `dna-assembly` | 1 | 1 | 482.4 | 1033.5 | 0.124558 | 0.217169 |
| `torch-pipeline-parallelism` | 0 | 0 | 561.8 | 630.0 | 0.074452 | 0.077087 |
| `qemu-alpine-ssh` | 1 | 1 | 388.6 | 401.1 | 0.016173 | 0.028699 |
| `openssl-selfsigned-cert` | 1 | 1 | 25.6 | 45.5 | 0.004295 | 0.010414 |
| `regex-chess` | 0 | 1 | 622.7 | 2591.8 | 0.158020 | 0.349024 |
| `log-summary-date-ranges` | 1 | 1 | 25.5 | 17.2 | 0.005495 | 0.005341 |
| `model-extraction-relu-logits` | 1 | 1 | 431.7 | 109.8 | 0.099051 | 0.026269 |
| `path-tracing` | 1 | 1 | 403.4 | 1172.0 | 0.128554 | 0.327928 |
| `regex-log` | 1 | 1 | 293.4 | 163.4 | 0.087292 | 0.047926 |
| `caffe-cifar-10` | 1 | 1 | 1931.2 | 2142.1 | 0.063456 | 0.082280 |
| `mteb-leaderboard` | 1† | 1 | 576.7 | 1169.3 | 0.081621 | 0.091648 |
| `llm-inference-batching-scheduler` | 1 | 1 | 364.5 | 638.2 | 0.097117 | 0.078021 |
| `pytorch-model-recovery` | 1 | 1 | 228.2 | 496.0 | 0.042237 | 0.084207 |
| `circuit-fibsqrt` | 1 | 1 | 1980.6 | 1289.7 | 0.174148 | 0.144138 |
| `merge-diff-arc-agi-task` | 1 | 1 | 48.6 | 42.3 | 0.014626 | 0.010407 |

Raw paired counts: {"both_fail": 1, "both_pass": 18, "improvement": 1}.
Common eligible paired counts: **17 both pass,
1 both fail, 1 candidate improvement,
0 candidate regression, 0 unscored**.
Excluded task pairs: `mteb-leaderboard`.
Exclusion prevents contaminated passes from being treated as ability evidence;
it is not evidence that a contaminated trial would otherwise have failed.

## Usage and runtime outcomes

| Metric | Main | Candidate |
| --- | ---: | ---: |
| Official passes (20 planned) | 18 | 19 |
| Scored failures | 2 | 1 |
| Unscored completed trials | 0 | 0 |
| Setup failures | 0 | 0 |
| Verifier errors | 0 | 0 |
| Agent seconds | 11160.416 | 13570.056 |
| Model attempts | 489 | 663 |
| Incomplete model attempts | 0 | 0 |
| Truncated responses | 3 | 0 |
| Recovery events | 2 | 0 |
| Known estimated USD | 1.457519808 | 1.898564712 |
| Prompt tokens | 22,442,386 | 48,471,106 |
| Completion tokens | 1,024,547 | 1,211,315 |
| Cached tokens | 22,124,668 | 47,946,752 |

Usage, cost estimates, and agent intervals are complete for all forty trials.
The candidate's total estimated cost changes by **+30.3%** and its summed
agent time by **+21.6%**. These totals include contaminated trials, and
sum task execution intervals rather than elapsed wall time. They exclude setup,
verifier work, the abandoned candidate, and the later single-task follow-up.
Missing or cancelled rows from separate experiments are never silently treated
as zero-cost scored failures.

On the common 19 eligible tasks, main used 10583.7 agent seconds
and $1.375899; the candidate used
12400.7 seconds and $1.806916.

The main model-extraction trial passed after a genuine `max_tokens` event and its
one permitted recovery. That is evidence about the existing recovery mechanism,
not an improvement caused by the candidate prompt. Main's chess-regex trial
instead hit `max_tokens` twice: one recovery was attempted, the second truncation
stopped the run, and `/app/re.json` was never created. The official tests completed
and scored zero. Its native terminal record has status `completed` but outcome
`response_truncated`; successful process finalization must not be confused with
successful task completion.

All non-passing rows: control `torch-pipeline-parallelism` (scored, reward 0.0); treatment `torch-pipeline-parallelism` (scored, reward 0.0); control `regex-chess` (scored, reward 0.0).

Native terminal outcomes: main `{"completed": 19, "response_truncated": 1}`; candidate `{"completed": 20}`. These are separate from official rewards.

## What the trajectories show

- Both pipeline-parallelism implementations failed official backward-activation
  comparisons. The candidate's toy-model consistency checks did not establish
  compatibility with the actual model tested by the verifier. This shows a gap in
  the checks, without establishing a unique underlying algorithmic cause.
- Model extraction passed in both arms. The candidate used about 110 agent seconds,
  compared with 432 for main, with no candidate truncation. Both inspected the
  task-provided `forward.py` and used its parameters for diagnostic comparison;
  their submitted extraction algorithms use `forward()` queries. This local
  diagnostic access is disclosed separately from external hidden-test exposure.
- Scheme passed in both arms without truncation. Candidate work took about 537
  seconds versus 1,418 for main. Both compared against the provided interpreter
  and its 32 sample programs; main spent longer exploring deeper self-evaluation.
- Circuit synthesis passed in both arms. The candidate checked the actual simulator
  with stratified, random, and boundary inputs plus intermediate-state invariants,
  taking about 1,290 seconds versus 1,981 for main. Main ran a more extensive
  exhaustive state sweep; both stayed within the task constraints.
- The direction reverses on other tasks: the candidate spent more time on model
  recovery, DNA assembly, and image reconstruction. Main already performed
  substantial independent and boundary validation on several tasks, including
  randomized regex-log checks. More explicit instructions do not imply that
  the control lacks those behaviors.
- In path tracing, the public description says normalized L2 similarity without
  specifying the formula. The official test uses cosine similarity, for which
  the candidate obtained about 0.99993 and passed. Its alternative
  `1 - ||a-b|| / ||b||` diagnostic was about 0.98823. That alternative is not the
  official score. The controller inspected the verifier formula only after both
  outputs were fixed; no test details were added to the prompt. Main inspected
  the task-provided executable; the candidate reconstructed the scene from its
  image and spent longer resolving numerical differences.

The candidate passed regex-chess after using the supplied checker and a general
chess library for independent random and boundary checks. It completed 73 model
attempts in about 2,592 seconds without truncation. This is the observed paired
improvement over main's missing artifact, with substantially more task work.
One stochastic pair does not isolate which prompt paragraph caused the change.

## Information-boundary findings and preserved abandoned runs

The first P0 candidate, before the information boundary, downloaded the pipeline
task's reference implementation and hidden evaluation source from an external
benchmark mirror. It then described its implementation as matching that exact
reference. The candidate arm was interrupted at 15:06 UTC. All five started
trials are preserved: **three passes, one installation failure before model work,
and one contaminated trial cancelled during verification**. Fifteen candidate
trials never started. These records are not replaced by or combined with the
new candidate's outcomes. See the [original-candidate audit](../results/headless-p0-original-candidate-audit-20261007.json)
and [original plan](../configs/headless-p0-20261007/experiment.json).
The abandoned arm's additional known estimated model cost is **$0.231970**;
the installation failure made no model calls and therefore has zero inference
cost. This extra cost is outside the comparison table above.

A retrospective check also confirmed the same integrity problem in the released
v0.9.0 baseline's passing pipeline trial: it downloaded the task repository,
read the solution and evaluation tests, and ran the copied tests. Its old raw
reward remains unchanged, but that pass is ineligible as independent-capability
evidence. The historical **18/20 is a preserved raw score**, not a clean causal
control for this experiment. See the [historical audit](../results/v0.9.0-pipeline-integrity-audit-20261007.json)
and the annotation in the [original report](v0.9.0-baseline-20261005.md).
A targeted scan of the other nineteen historical trajectories found no matching
retrieval pattern; this is not an exhaustive retrospective audit.

The contemporaneous main MTEB trial also has confirmed contamination. It first
researched task-authorized public leaderboard data, then fetched the exact
Terminal-Bench task's reference solution, README, and hidden test source from
Hugging Face. ATIF step 99 contains the retrieved expected answer; step 101
writes the final result. Its raw reward remains one, but the MTEB pair is excluded
from the common eligible comparison. Public MTEB results are legitimate task
inputs; Terminal-Bench's answer and evaluation source are a different category.

Main's pipeline trial attempted exact-function searches but received a security
checkpoint or no result links; no answer/test contents were observed. The
structured results retain per-trial audit notes and trajectory hashes for all
forty trials. Audit findings describe observed retrieval, not proof that all
possible contamination mechanisms have been excluded.

The guarded MTEB trial passed using task-authorized public leaderboard data. It pinned the results repository to August 2025, checked coverage of all requested tasks, reproduced the public aggregation path, and independently cross-checked raw JSON scores. No Terminal-Bench reference-answer or hidden-test retrieval was observed. Its passing result remains visible even though the contaminated control makes the MTEB pair ineligible for a common capability comparison.

All forty trajectories were audited: 1 had confirmed external task-answer/test exposure; 39 had no confirmed exposure in this review.

## Separate follow-up: permit task-supplied workspace references

The 368-word guard discouraged legitimate use of a supplied executable in the
path-tracing trial: the agent noticed it but declined disassembly because the
task text did not name it. After all eight pilot20 jobs had frozen their inputs,
commit `e61558f3ef23e626b7341b9811ec66044ce8610b` clarified that task-supplied
source, executables, and tests are available unless the task restricts their use.
The boundary against externally obtained task answers and hidden tests remains.
No task name, filename, algorithm, answer, or verifier formula entered the prompt.

The current prompt has 385 words, SHA256
`37c4d9d44640c0051dc5a20e5954a067b98e8c51be07a48f080aa059e725c55d`.
Its [single-task plan](../configs/headless-workspace-20261007/experiment.json)
was registered before one fresh path-tracing run from an isolated checkout.
The run waited for a full-comparison arm to finish so concurrency stayed at most
two. See the [follow-up evidence](../results/headless-workspace-followup-20261007.json).

The clarified candidate **passed** the official verifier on its first attempt.
It disassembled the supplied executable (ATIF step 29 and subsequent reads),
implemented a C renderer, and checked a clean static build against the supplied
image byte for byte. No external answer/test retrieval was observed, and no
reference-boundary refusal was observed in this trial.

| Path-tracing variant | Official reward | Agent seconds | Model attempts | Estimated USD |
| --- | ---: | ---: | ---: | ---: |
| Main, 175 words | 1 | 403.401 | 30 | 0.128554 |
| Full20 candidate, 368 words | 1 | 1171.983 | 70 | 0.327928 |
| Clarified candidate, 385 words | 1 | 340.510 | 44 | 0.114759 |

The follow-up has complete usage/cost accounting, no truncation or recovery,
and an installed wheel matching its pinned source and manifest. Its additional
estimated cost is **$0.114759**, outside the full comparison totals. The dependency
profile remains explicitly `not_configured`. This observed use of supplied
material supports the wording clarification; one selected case cannot establish
that the wording caused the timing difference or that other tasks improve.

This is one case selected after observing an efficiency regression and prompt
ambiguity. The earlier path trials are descriptive comparators, not randomized
repeat samples. All earlier outcomes remain intact. The clarified prompt has
**not** been rerun across all twenty tasks; its result cannot be presented as
a new pilot20 score.

## Next optimization to test separately

The clearest operational follow-up is to make the actual Bash tool contract
explicit: its call limit is 120 seconds, a shell `timeout 1500` cannot extend it,
and a long command needs a correctly redirected background launch plus polling
for completion and exit status within the overall task budget. Preserve usable
intermediate deliverables before expensive searches or checks. Services that the
task requires to remain running are distinct from unfinished artifact generation.

This is grounded in observed failures, not just a prompt preference. Installers
in multiple pipeline/tensor trials used `cd ... && nohup ... >log 2>&1 &`, which
can leave the background AND-list's shell holding the captured pipes. The tool
then waits and kills the command session at its timeout. The guarded batching
scheduler also ran `timeout 1500 python3 run4.py ...` and was interrupted at the
actual 120-second tool limit.

The [scaled local diagnostic](../results/headless-tool-limit-probe-20261007.json)
uses the unchanged Bash implementation with a 0.25-second tool limit and a
2-second workload. The problematic conditional-background form times out;
redirecting the whole group returns immediately and its completion marker is
observed. An inner 1,500-second timeout still loses to the outer 0.25-second limit.
These probes establish tool semantics, not model compliance or a score gain.
No tool implementation or tool guidance was changed during this comparison.

A subsequent candidate should test this operational guidance and earlier runnable
deliverables separately, with the information boundary shared by both variants.
Repeat difficult cases and add held-out tasks before claiming stable capability
or efficiency gains. Keep all failures and every observed regression, rather than
replacing results until a favorable score appears.

## Repository checks

Core tests: **351 passed, 4 skipped**. Harbor workflow tests: **91 passed**.
Both the frozen candidate and the workspace-reference clarification passed CI
on Python 3.13 and 3.14 and the Harbor workflow contracts. No brittle prompt-text assertion tests were added. Development notes
are updated together in Chinese and English; research-note sources are unchanged.
Raw benchmark evidence remains in the referenced Git-ignored `jobs/` directories.
