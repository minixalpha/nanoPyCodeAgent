# Truncation recovery: three additional runs per task

The six predeclared fresh runs scored **4/6 passed**, **2 scored failures**, and
**0 unscored trials**. Model extraction passed **1/3**; Scheme passed **3/3**.
One model-extraction run naturally truncated on its second response, reproducing
the released baseline's failure pattern. Automatic recovery continued useful
work, but that trial still failed the official test. The experiment demonstrates
live continuation after truncation, not successful recovery of a passing score.

## Fixed experiment

The maintainer requested three additional runs of each previously failed task
after the [initial two-run experiment](truncation-recovery-20261005.md) passed
without any truncation. The [plan](../configs/truncation-recovery-repeat3-20261005/experiment.json)
was committed before model work, with all six jobs and their queue order fixed.
Every job ran once in a fresh container; no outcome was replaced or retried.

- Checkout: `382cb38413d7d5368ad1be97e85142f280172a5b`.
- Wheel version: `0.9.1.dev5+g382cb3841`.
- All 21 agent/adapter Python source hashes match the earlier experiment at
  `e1be6ed1f81a17d73677b414d4d913adb81e9e25`. This round changes no runtime code.
- Model: `deepseek/deepseek-flash`, official
  `https://api.deepseek.com/anthropic` endpoint.
- 100 model replies, 65,536 output tokens per reply; 720 seconds of work for
  model extraction and 2,220 seconds for Scheme; 1,800 seconds for setup.
- Two simultaneous single-task jobs at most, using the repository's standard
  Harbor entry point and verified dependency cache.
- Original task revisions, images, package sources, and tests. Verifier limits
  remain 900/2,400 seconds per attempt; only timeouts may retry, at most three
  attempts on the same output. All six verifiers completed on their first attempt.

Both install-only trials passed. Both verifier dependency profiles explicitly
report `not_configured`; these are installation successes, not certification of
verifier dependencies. The preflight and all six run wheels are byte-identical,
with SHA256 `9f519124b62314d5b3625004441e0bfc29473533f29cef2dcf3640e55094800f`.
Both full task checksums and image IDs match the released baseline. All 73
recorded task-file hashes remained unchanged. All six native ATIF trajectories
validate, and all six native terminal outcomes are `completed`.

The six jobs ran from **2026-10-05 14:27:47 to 15:20:14 UTC**, including setup,
model work, verification, and cleanup. The [reproduction instructions](../configs/truncation-recovery-repeat3-20261005/README.md)
record the fixed schedule and standard commands.

## All six results

| Task | Run | Reward | Truncations | Recoveries | Model replies | Largest reply tokens | Agent seconds | Official result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Model extraction | 1 | 0 | 0 | 0 | 27 | 17,791 | 414.4 | Missing rows 2, 27 |
| Model extraction | 2 | 0 | 1 | 1 | 17 | 65,536 | 554.1 | Missing rows 24 |
| Model extraction | 3 | 1 | 0 | 0 | 23 | 53,538 | 483.9 | Passed |
| Scheme | 1 | 1 | 0 | 0 | 41 | 17,495 | 1080.7 | 63/63 subcases |
| Scheme | 2 | 1 | 0 | 0 | 79 | 35,869 | 1281.1 | 63/63 subcases |
| Scheme | 3 | 1 | 0 | 0 | 60 | 23,002 | 829.9 | 63/63 subcases |

Agent seconds include finalization overhead. Missing-row indices are zero-based.
The largest-reply count includes internal thinking tokens reported by the
provider, not only visible text. Scheme passed all 63 subcases in every run,
including the nested self-interpretation cases that failed in the baseline.
None of these Scheme runs exercised recovery.

Known token-based estimated cost: **$0.906352500**. All six trials have complete
usage and cost accounting for reported tokens, with no incomplete model streams.
These estimates use the static DeepSeek price table and are not provider bills.

## What happened after the observed truncation

Model-extraction run 2 first inspected the environment. Its second response
consumed exactly 65,536 output tokens and ended with `max_tokens`, with no tool
calls to execute. This reproduces the relevant baseline pattern: long reasoning
before creating the required script.

At **326.302 seconds**, with about **393.698 seconds** left in the original
720-second budget, the agent injected its single `truncation_recovery` prompt.
It then completed **15 more model responses** and **14 tool executions**,
including writing `/app/steal.py`, editing it, and running local checks. No
second truncation occurred. The native run completed at **552.428 seconds**;
neither the original deadline nor the reply/token caps were increased.

The official verifier ran the submitted script and found its output file.
The script reported recovering **29 hidden neurons** from the verifier's
30-neuron network; original weight row **24** had no matching output row.
Therefore the official reward remained **0**. This was a solution-quality
failure after productive continuation, rather than the baseline's missing
script/output failure. The old stop-on-first-truncation rule would have stopped
at the same truncation boundary; this run supplies direct evidence that the
new branch continues beyond it. It does not supply a paired estimate of the
policy's effect on final task success.

Model-extraction run 1 also created its script and output, then ended voluntarily
without truncation. Its official test failed on rows **2 and 27**. Run 3 passed
without truncating. The verifier replaces the visible 20-neuron example with a
30-neuron network; passing checks against the visible example alone does not
establish complete extraction for the official case. The observations support
investigating validation and extraction completeness separately from truncation
handling, but do not establish a single algorithmic root cause.

## Interpretation and evidence

The branch now has a real example of **one truncation followed by useful tool
work within the original budget**. This six-run sample has **zero passing
trials that used recovery**, so it does not show that recovery rescues the final
score. It also contains no Scheme truncation with which to test recovery on
that task. Keep these conclusions separate from the deterministic tests of the
once-per-run cap, partial-tool safety, and budget boundaries already recorded in
the initial experiment.

The [structured results](../results/tb21-truncation-recovery-repeat3-20261005.json)
preserve every trial, its original result/trajectory/verifier-log paths,
per-attempt verifier records, source/artifact checks, accounting completeness,
and the sequence of model/tool activity after recovery. Raw artifacts remain
local in the referenced Git-ignored `jobs/` directories.

The earlier 2/2 experiment remains a separate sample. The released v0.9.0
[pilot20 baseline](v0.9.0-baseline-20261005.md) remains **18/20**. Fresh model
paths and different concurrent pairings prevent attributing aggregate score
differences to this change; three runs per task also provide only a small sample.
No extra runs were added after observing these results.
