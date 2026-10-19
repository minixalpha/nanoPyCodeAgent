# Common-main baseline: all 34 development tasks

All 34 tasks received one fresh model trial on main
`2eb99b608dfb39464d17d109a4a8f11afda607a9`: **28 passed and six failed
(82.35%)**. Every official verifier executed tests. The model phase had zero
setup errors, zero verifier errors, and zero verifier retries.

One passing trial, `torch-tensor-parallelism`, accessed external Terminal-Bench
revision metadata. Its official pass is retained and the exposure is reported
separately below. This is an already exposed development pool, not a held-out
benchmark or a claim of evaluation without external benchmark-material access.

The [machine-readable results](../../results/dev34-main-baseline-20261012.json)
contain all trial identifiers, source/task/configuration provenance, native
scores, test counts, timing, partial usage, failure diagnoses, and evidence
hashes. Raw trajectories and logs remain local because they can contain secrets.

## Runtime and protocol

Both local main and origin/main pointed to `2eb99b6` at registration. Experiment
files and transport utilities live on `benchmark/dev34-main-baseline-20261012`;
the evaluated agent and adapter came from a separate, unchanged checkout of
that main commit. No agent or prompt optimization was included.

| Property | Value |
| --- | --- |
| Pool | Previously exercised 22 tasks plus the 12 additions |
| Dataset | `terminal-bench/terminal-bench-2-1`, 89-task catalog |
| Dataset revision | `sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a` |
| Model | `deepseek/deepseek-flash` |
| Endpoint | Official DeepSeek Anthropic-compatible endpoint |
| Prompt | Main's 385-word headless prompt |
| Limits | 100 replies; 65,536 output tokens per request |
| Sampling | Temperature and reasoning effort unset |
| Model trials | Exactly one per task; no replacements or whole-trial retries |
| Queue | Ascending work budget, then name; consecutive pairs; concurrency two |
| Setup | Separate 1,800-second budget |
| Agent work | Native task timeout minus 180 seconds |
| Verifier | Original per-attempt limit; timeout-only retries allowed, none used |

The final [v5 registration](../../configs/dev34-main-baseline-20261012/experiment-v5.json)
has SHA256 `f7bc7b329767f4b8007956462f6cdbd4407d386af493524df27ba313c0a4e4c3`.
All 34 jobs installed the same wheel, SHA256
`f4dcc18758e584696f955ae57fd18c751599b70e8b497ca2db7ef9e2b16e9350`.
The prompt SHA256 is
`37c4d9d44640c0051dc5a20e5954a067b98e8c51be07a48f080aa059e725c55d`.

The standard runner was invoked from `jobs/dev34-baseline-main-source` through
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`.
Source snapshots, installed wheel digests, complete task-file hashes, accepted
preflight provenance, configuration hashes, and queue barriers were checked for
every job. All 34 original image IDs and registry digests were unchanged in the
post-run audit, and no scored-trial containers remained.

All outputs froze at **2026-10-12 22:12:55 UTC** before new trajectory or
hidden-test-content review. The freeze manifest is embedded in the results JSON.
Existing pilot, repeat, and twelve-task results were not reused in this score.
The remaining 55 packages stayed unopened.

## Per-task results

Test counts below come from official pytest stdout and include parameterized
cases. Native CTRF summaries are preserved separately: they deduplicate function
names for pipeline parallelism (3 instead of 4 tests) and tensor parallelism
(3 instead of 13). Agent seconds include its model/tool work, not setup or the
official verifier.

| Task | Raw reward | Tests passed / failed | Agent seconds |
| --- | ---: | ---: | ---: |
| adaptive-rejection-sampler | 0 | 0 / 9 | 720.3 |
| build-cython-ext | 1 | 11 / 0 | 586.5 |
| cancel-async-tasks | 1 | 6 / 0 | 378.9 |
| cobol-modernization | 1 | 3 / 0 | 551.7 |
| db-wal-recovery | 0 | 5 / 2 | 359.6 |
| fix-code-vulnerability | 1 | 6 / 0 | 58.7 |
| git-multibranch | 1 | 1 / 0 | 238.2 |
| kv-store-grpc | 0 | 5 / 2 | 439.2 |
| log-summary-date-ranges | 1 | 2 / 0 | 23.1 |
| merge-diff-arc-agi-task | 1 | 5 / 0 | 123.2 |
| model-extraction-relu-logits | 1 | 1 / 0 | 380.0 |
| multi-source-data-merger | 1 | 3 / 0 | 33.1 |
| nginx-request-logging | 1 | 8 / 0 | 70.0 |
| openssl-selfsigned-cert | 1 | 6 / 0 | 70.0 |
| pypi-server | 1 | 1 / 0 | 129.1 |
| pytorch-model-cli | 1 | 6 / 0 | 392.7 |
| pytorch-model-recovery | 1 | 5 / 0 | 363.6 |
| qemu-alpine-ssh | 1 | 1 / 0 | 555.5 |
| query-optimize | 0 | 5 / 1 | 373.8 |
| regex-log | 1 | 1 / 0 | 72.6 |
| torch-pipeline-parallelism | 0 | 2 / 2 | 720.9 |
| torch-tensor-parallelism (exposure flagged) | 1 | 13 / 0 | 559.6 |
| write-compressor | 1 | 3 / 0 | 394.3 |
| constraints-scheduling | 1 | 3 / 0 | 32.0 |
| custom-memory-heap-crash | 1 | 6 / 0 | 245.3 |
| dna-assembly | 1 | 1 / 0 | 1162.7 |
| llm-inference-batching-scheduler | 1 | 6 / 0 | 614.5 |
| path-tracing | 1 | 5 / 0 | 259.9 |
| schemelike-metacircular-eval | 1 | 1 / 0 | 1777.1 |
| caffe-cifar-10 | 1 | 6 / 0 | 2448.9 |
| circuit-fibsqrt | 1 | 3 / 0 | 610.7 |
| mteb-leaderboard | 1 | 2 / 0 | 1380.4 |
| regex-chess | 0 | 2 / 2 | 2818.8 |
| build-pov-ray | 1 | 3 / 0 | 338.1 |

Overall, pytest executed 155 cases: 137 passed and 18 failed, with no skips or
errors. The task score remains 28/34; individual test cases are not equally
weighted tasks. The previous 22-task subset scored 19/22 and the twelve additions
scored 9/12 in this run.

## Why the six tasks failed

Step references are ATIF `step_id` values in each locally retained trajectory.
The result JSON binds those files and official outputs by SHA256.

| Task | Observed failure | Verification lesson |
| --- | --- | --- |
| adaptive-rejection-sampler | No `/app/ars.R` was submitted. Installation delays and interrupted model streams exhausted the 720-second work budget. | Produce a minimal deliverable early; bound installation and recovery work. This run provides no evidence about a submitted ARS algorithm. |
| db-wal-recovery | Opening the original SQLite database discarded its encrypted WAL before backup. Guessed values missed WAL updates. | Preserve all inputs and sidecars before stateful reads; validate recovered values against original evidence. |
| kv-store-grpc | `SetValRequest` used `val`; the task required `value`. The self-client used the same incorrect schema. | Derive an independent API contract from the specification. Self-consistency does not prove interface compliance. |
| query-optimize | Output was correct, but the query was too slow against the official optimized reference. | Establish repeatable target-runtime measurements and test candidate query plans after correctness is established. |
| torch-pipeline-parallelism | Layer calls lacked required rotary position embeddings. A real self-test found the error near the deadline. | Test the installed API with a tiny forward/backward pass early; propagate process failures and leave repair time. |
| regex-chess | Castling was allowed when the white king was already in check. | Supplement random differential tests with explicit negative cases for each special-rule precondition. |

### Sampler: missing output after interrupted execution

Installation calls at steps 5, 9, and 13 each hit the bash timeout, including
attempts to launch background work. R was available by step 15, roughly 6.5
minutes into the work budget. The next two model calls ended in
`RemoteProtocolError` after approximately 241 and 29 seconds; the last call
reached the deadline after another 58 seconds. No implementation write completed.

All nine official tests ran and failed on the missing file. This is a scored
failure with an operational cause, not a setup failure or a demonstrated
algorithmic error. The registered preflight did not cover R installation.

### WAL recovery: preserving evidence must precede inspection

Step 5 inspected part of the WAL and opened the original database concurrently.
SQLite discarded the invalid encrypted WAL. Backup/decode attempts at step 7
came too late. The final JSON contained 11 plausible fruit records with values
following `id * 100`, and shape/count checks passed. Two official tests caught
incorrect values, including `100` where the recovered value should have been
`150` for id 1. The final agent message at step 53 disclosed the lost WAL and the
inference; this was not an undisclosed claim of successful recovery.

### gRPC: an independent consumer would have caught the mismatch

Step 7 defined `SetValRequest.val`. Tests at steps 9, 13, 23, and 37 used the
generated client and the same field. They exercised real RPCs, overwrites,
independent keys, empty keys, and an integer boundary, but never constructed the
request specified by the task. Official calls using `value=999` and `value=42`
failed before reaching the server. A descriptor assertion or independently
specified client would address the actual gap.

### SQL: correct results are insufficient for a performance task

The verifier measured a reference median of **0.291814 s** and a solution median
of **0.371624 s**, about 27.35% slower; the allowed multiplier was 1.05. The agent
did establish an exact 500-row output match and preserved the original database,
using indexes only on a copy to obtain reference output. Its attempted repeated
timing command at step 33 failed because `/usr/bin/time` was missing. Later
shell timings around 0.48 s looked good against the much slower original query.

The optimized reference and precise threshold were hidden from the agent.
The actionable gap is reliable comparative performance work and optimization
margin, not expecting the agent to know the hidden reference.

### Pipeline parallelism: verification started too late

The implementation was written at step 11 before PyTorch/Transformers were
available. The first substantive test, written at step 27, failed in a reference
test hook. After that hook was repaired, step 31 exposed
`TypeError: cannot unpack non-iterable NoneType object` when attention unpacked
`position_embeddings`. The deadline arrived before a repair.

Both official world-size tests reached submitted code and failed with the same
error; two structural checks passed. This is not a verifier installation error.
The self-test commands also piped output through `tail`, obscuring failing
process exit status. Early smoke tests, explicit process status, and bounded
distributed tests would make the remaining budget more useful.

### Regex chess: a large test count missed a specific negative condition

Two official games exposed an extra kingside castle from a position where the
white king on e1 was already checked: once by an e8 rook, once by a d3 knight.
The other game suite and the rule-size check passed.

Steps 107, 115, and 117 changed castling generation and attack-filter ordering.
The intermediate X0-to-X1 state was still created before the first filter, so
it could survive even when the initial king position was attacked. Later
castling states could consequently escape that initial check.

The final implementation had substantive independent verification against
`python-chess`: 618 sampled positions in one collection and 600 in another
passed after the final changes, as did the supplied check script. These counts
do not imply unique positions or complete rule coverage. Explicit examples of
castling out of check, through check, and into check were needed; the final claim
that all three were excluded exceeded the evidence.

## Dependency preparation and environment preservation

Slow or interrupted downloads required amendments **before any model trial**.
The historical attempts remain recorded separately from the 34 scored trials.

| Install-only plan | Attempts | Successful | Setup errors | Cancelled / interrupted |
| --- | ---: | ---: | ---: | ---: |
| v1 | 6 | 0 | 5 | 1 |
| v2 | 9 | 0 | 7 | 2 |
| v3 | 34 | 29 | 3 | 2 |
| v4 | 5 | 5 | 0 | 0 |
| Total | 54 | 34 | 15 | 5 |

V1 encountered setup timeouts and uv TLS errors. V2's host proxy was unreachable
from task containers and was stopped. V3 used isolated loopback sidecars and
completed 29 installations; two uv archive downloads and one managed-Python
download failed, and two remaining installations were interrupted to apply the
verified archive cache. V4 completed the five unresolved installations.

V5 accepted the 29 successful v3 records and five v4 records only after complete
native provenance checks. QEMU's registered `qemu-alpine-ssh-v1` verifier
dependency profile passed. The other **33 profiles are `not_configured`**;
successful agent installation does not certify their verifier dependencies.
All install-only trials ran no models or official task assertions.

The final transport cached original immutable APT indexes and original uv / GNU
CPython release archives with full digest verification. Mutable APT release
metadata and packages were not proxy-cached; native APT verification remained.
Release-cache hits required matching filename, size, and SHA256. Original
package origins, Python selection, task images, resources, official scripts,
and verifier per-attempt time limits were preserved. Model/API traffic used its
normal route.

Each task had separate cache sidecars in its own network namespace, no published
ports, no task filesystem or credential mounts, and separate CPU/memory limits.
All 34 model trials used the final v5 transport. Details, original failure
evidence, manifests, and network integration probes are linked from the
[run configuration README](../../configs/dev34-main-baseline-20261012/README.md).
The supporting Harbor workflow suite passed **167 tests** before model work;
the corresponding branch commit also passed all three CI checks.

## Exposure and publication audit

All 34 frozen trajectories were scanned for benchmark references, verifier
paths, external hosts, and exact provider credential values. Flagged commands
and returned observations were reviewed alongside the six failure traces.

- **Tensor parallelism:** exact task-phrase searches at steps 15–23 reached a
  Terminal-Bench dataset README. Step 23 returned revision metadata; step 25
  fetched the external README and displayed its pre-scattered-input clarification.
  That requirement was already present in the supplied instruction. No solution
  code or hidden test content was observed in these results. The pass remains
  official raw reward 1, with benchmark-material exposure explicitly flagged.
- **Local test paths:** tensor parallelism probed an absent `/app/tests`; WAL
  recovery and Git multibranch listed empty verifier-log directories. Other
  flagged paths were public upstream tests or agent-created tests/data.
  Memory-crash benchmark references were preserved source canary comments.
- **Other network activity:** reviewed accesses concerned dependencies, upstream
  projects, CIFAR data, NEB documentation, and the public MTEB/Scandinavian
  leaderboard sources relevant to those tasks. No other benchmark-answer
  retrieval was observed in this review.
- **Credentials:** WAL recovery's environment inspection exposed the provider
  credential to its own tool observations at steps 27 and 49. Those raw traces
  remain local and are not included in the PR. No transmission of that credential
  to another external destination was observed in the reviewed commands.

This audit cannot prove absence of all exposure or training contamination.
It does not retroactively remove tasks, replace trials, or change native rewards.
Future experiments should declare and enforce an external benchmark-material
policy before execution and prevent task tools from reading provider secrets.

## Time, cost, and comparison limits

The model jobs ran from approximately **17:29 to 22:12 UTC on October 12**:
**283.25 minutes** elapsed, excluding dependency preflight. Summed agent work
was 321.38 minutes, agent installation 32.96 minutes, and verifier time 50.01
minutes; these sums differ from wall time because of concurrency and pair
barriers.

Recorded usage totals 60,464,780 prompt tokens (59,660,798 cached) and 1,603,196
completion tokens. The **known estimated cost subtotal is $2.523**, not a complete
bill. Usage/cost records are incomplete for the sampler and pipeline trials;
missing calls have not been priced as zero.

The [earlier twelve-task baseline](dev12-main-baseline-20261011.md) used the
same main commit and scored 10/12. Those tasks score 9/12 here: PyTorch CLI
changed from fail to pass, sampler and SQL changed from pass to fail, and WAL
recovery failed in both. Trial randomness and transport/environment history
differ; this is not evidence of an agent code improvement or regression.

The 34-task pool remains useful for development: retain all 28 passing tasks as
regression checks and use the six failures for diagnosis. Agent experiments
should use matched baseline/candidate repeats under the same registered
conditions, measuring task pass rate, verification evidence, time, and exposure
separately. One pass does not establish task stability. Keep the remaining 55
unopened tasks for a later, predeclared evaluation after choosing the candidate.

The next agent changes suggested by this evidence are input preservation,
independent contract checks, early execution of small tests, reliable exit/error
reporting, targeted negative cases, and repeatable performance measurements.
These are hypotheses for a subsequent experiment; none was applied to this run.
