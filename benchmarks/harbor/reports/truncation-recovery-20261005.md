# Bounded truncation recovery: two-task experiment

The experimental agent scored **2/2 passed**, with **0 scored failures** and
**0 unscored trials** on the two tasks that failed in the frozen v0.9.0
pilot20. Neither trial reached the generation cap, so neither exercised
automatic recovery. These fresh-run scores do not establish a benefit from the
policy. Deterministic tests cover the recovery branch and its safety/budget
boundaries; live effectiveness remains unproven.

## Hypothesis and implementation

A completed API response with `stop_reason="max_tokens"` previously ended the
headless run even when task time and replies remained. Allow one continuation
per headless run, using the original deadline, reply count, and per-reply token
limit. Keep partial visible text and a notice in request history; discard all
unexecuted tool calls and incomplete thinking from that response. Continue from
confirmed tool results and current files, without replaying prior tool actions.

Record the continuation as `input.injected` with reason `truncation_recovery`,
while retaining each model attempt's stop reason, usage, and cost. A transport
retry or successful tool action does not renew the allowance. Another
truncation, the reply limit, or the original deadline ends the run. Interactive
mode continues to return to the user after a truncation.

## Fixed inputs

- Agent commit: `e1be6ed1f81a17d73677b414d4d913adb81e9e25`.
- Model: `deepseek/deepseek-flash` at `https://api.deepseek.com/anthropic`.
- 100 model replies and 65,536 generated tokens per reply.
- Model extraction: 720 seconds of work; Scheme: 2,220 seconds of work.
- Setup allowance: 1,800 seconds, unchanged from the frozen release baseline.
- One fresh run per task, no whole-trial retry. The two single-task standard
  Harbor jobs ran together with at most two simultaneous trials.
- Official task revisions, images, package sources, and tests were preserved.
  All 73 recorded task-file hashes remained unchanged, and task checksums
  match preflight. Verifier timeouts alone may retry at the original per-attempt
  limit, at most three attempts on the same agent output.

The [predeclared plan](../configs/truncation-recovery-20261005/experiment.json)
contains the task revisions, budgets, source/config hashes, and analysis rules.
Both install-only checks passed with the experimental agent. Both verifier
dependency profiles explicitly report `not_configured`; installation success
is not verifier dependency certification.

The preflight and both live-run wheels are byte-identical. Both task images and
full task checksums match the released baseline. Both official verifiers
completed on their first attempt; Scheme passed all 63 subcases.

## Results

| Task | Baseline reward | Experiment reward | Native outcome | Truncated responses | Recoveries | Executed tools after recovery | Agent seconds | Known estimated USD |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `model-extraction-relu-logits` | 0 | 1 | `completed` | 0 | 0 | 0 | 361.7 | 0.054624 |
| `schemelike-metacircular-eval` | 0 | 1 | `completed` | 0 | 0 | 0 | 1398.5 | 0.180475 |

Known estimated cost subtotal: **$0.235099**.
Usage accounting is **complete**;
cost accounting is **complete for reported tokens**.
There are 0 incomplete model attempts. Costs use the static
DeepSeek price table and are not provider billing totals. Agent seconds include
finalization overhead.

The [structured results](../results/tb21-truncation-recovery-20261005.json)
include both trials, preflight, source/wheel hashes, recovery-event counts,
per-attempt verifier records, native outcomes, and usage. Raw journals,
trajectories, and test logs remain in the referenced Git-ignored `jobs/` paths.

## Validation and interpretation

- Core tests: 351 passed, 4 optional-transport skips with locked dependencies;
  355 passed with Anthropic SDK 1.5.0.
- Harbor workflow/ATIF contracts: 91 passed, including truncated tool calls
  followed by a recovered model response.
- Deterministic tests exercise continuation through tool work to completion,
  the once-per-run cap across transport retries, unchanged deadlines and reply
  limits, discarded truncated tools/thinking, no duplicate committed tool
  execution, unchanged interactive behavior, and retained usage/cost totals.
- Live trajectory validation and source/task integrity checks are recorded in
  the structured results.

The [released baseline](v0.9.0-baseline-20261005.md) remains **18/20**. These two
new results do not replace its failures or produce a revised pilot20 score.
They use fresh model generations and a different concurrent task pairing;
there is no deterministic counterfactual for the old failed responses.

## Follow-up

The maintainer subsequently requested a fixed set of three additional runs per
task. The [separate six-run report](truncation-recovery-repeat3-20261005.md)
records 4/6 passes and one natural truncation followed by useful continuation,
but no passing score after recovery. The original results above remain unchanged.
