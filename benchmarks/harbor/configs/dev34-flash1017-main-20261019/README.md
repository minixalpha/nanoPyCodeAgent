# Current-main dev34 baseline with DeepSeek Flash 1017

**Completed:** 26 passes, five scored failures, and three unscored verifier errors. All 34 tasks started a fresh agent trial. See the [English report](../../reports/en/dev34-flash1017-main-20261019.md), [complete Simplified Chinese report](../../reports/zh-CN/dev34-flash1017-main-20261019.md) and [audited results](../../results/dev34-flash1017-main-20261019.json). Native zero rewards for pre-assertion verifier failures remain preserved; analytical scores are null. The CLI dependency failure followed agent-forced package installations. A passing Scheme evaluator uses a host depth-counter workaround, recorded separately.

This registration runs all 34 existing development tasks once with fresh model
outputs from current main `ce28b1e826a292d796ba64f13e79199b66f65758`. The experiment branch and its independent
runtime checkout are separate, so recording results cannot change the evaluated
source. Historical scores and outputs remain separate.

## Frozen inputs and limits

- [Active plan](experiment-v2.json): source, model mapping, task and infrastructure hashes,
  budgets, installation preflight, and the complete fixed queue.
- [Selection](selection.json): the unchanged dev34 pool and pinned task revisions.
- [Prompt](main-prompt.txt): current main's 385-word headless prompt.
- [Images](image-digests.json): image identities checked before execution.
- Runtime checkout: `jobs/main-source`, detached at `ce28b1e826a292d796ba64f13e79199b66f65758`.

The model is `deepseek/deepseek-flash` at the official DeepSeek Anthropic endpoint.
[Official documentation](https://api-docs.deepseek.com/quick_start/agent_integrations/)
was checked on 2026-10-19 and maps this alias to DeepSeek-V4.1-Flash-1017. The
alias does not pin an immutable checkpoint. Temperature and reasoning effort are
unset. Each task allows 100 replies, 65,536 output tokens per reply, and its native
agent timeout minus 180 seconds for model work; setup separately allows 1,800
seconds. Original task images, resources, package sources, official scripts, and
per-attempt verifier limits stay unchanged.

Run fresh installation checks for all 34 tasks before starting any model work.
Only QEMU has a registered verifier dependency profile; the other 33 report
`not_configured`. Agent installation success does not certify those dependencies.
The verified APT index and original uv/Python archive caches retain upstream
filename, size, and SHA256 checks. The [archive manifest](dependency-release-manifest.json)
is reused unchanged from the October 18 run, including all five original archives.

The model queue sorts by ascending work budget and task name, with consecutive
pair barriers and maximum concurrency two. Every task generates exactly one new
output. Only verifier timeouts may retry, at most three total attempts with the
same output and original per-attempt limits. Dependency-error recovery remains
disabled. Setup failures and verifier errors are recorded separately from scored
failures; a zero without executed assertions is analytically unscored.

## Installation preflight history

All 34 tasks now have fresh, successful native installation-only records from
this frozen checkout. The first batch completed 33 installations and recorded
one `NetworkConnectionError`: TLS failed while downloading the unchanged
`https://astral.sh/uv/0.9.11/install.sh` script for the Scheme evaluator. A new,
separately named installation-only trial for that task succeeded. No model or
official verifier ran during either preflight job.

The [original registration](experiment.json) and all 35 attempts remain intact.
[Native evidence](preflight-evidence.json) binds all results, bootstrap records,
source manifests, and input configurations by hash. The active v2 plan accepts
exactly one successful native record per task through the existing strict
orchestrator checks. Model configurations, task revisions, environment transport,
source, budgets, and timeout-only verifier policy remain unchanged. QEMU's
registered verifier profile passed; the other 33 remain `not_configured`.

## Execute

From this experiment worktree's repository root, supply credentials through the
process environment, set `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`,
and leave `ANTHROPIC_MODEL` and `ANTHROPIC_MAX_TOKENS` unset.

```bash
python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev34-flash1017-main-20261019/experiment-v2.json \
  --phase preflight

python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev34-flash1017-main-20261019/experiment-v2.json \
  --phase model
```

The existing orchestrator calls only the standard
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`
entry point from the frozen runtime checkout. Native jobs and input manifests
live under `jobs/main-source/jobs/`; orchestration records live under
`jobs/dev34-1017-main-20261019-orchestration/`. Existing jobs cannot be overwritten.

Inspect operational stages and completion metadata during execution, then freeze
all 34 outputs before reviewing new trajectories or hidden-test content. Raw logs
remain local; publish derived findings and evidence hashes after review. All 34
tasks have prior development exposure. The remaining 55 dataset tasks stay
unopened, and this run does not isolate a model-checkpoint effect.

## Host launch failures and supplemental jobs

Three primary jobs failed before any native trial or model output existed:
Git multibranch and gRPC KV store could not connect to the Harbor registry;
log-summary date ranges could not resolve wheel build requirements because the
PyPI TLS connection failed. The original empty summaries, logs, snapshots, and
job records remain intact, bound by [launch evidence](launch-failure-evidence.json).
These are host launch errors, separate from task setup, verifier errors, and
model correctness failures.

Three single-task supplemental plans register one new output for each task:
[Git](launch-recovery-git-multibranch.json),
[KV](launch-recovery-kv-store-grpc.json), and
[logs](launch-recovery-log-summary-date-ranges.json).
They use the exact same frozen main checkout, configurations, successful native
installation evidence, images, prompt, resources, and budgets. Original jobs
remain failed; generated outputs and scored results are never replaced.

Start these plans only when the original queue reaches its final pair and one
of those jobs has ended, leaving one free slot with no later primary jobs to
start. Execute the three single-task plans serially through the existing
orchestrator and standard entry point. Total task concurrency stays at two or
fewer. All primary and supplemental outputs must freeze before new trajectory
or official-test-content review. Report all original launch failures and the
supplemental scheduling separately from the original fixed queue.

All primary and supplemental jobs completed. The six relocated OCI archives and 44 cached blobs were restored and hash-verified. Final inspection retained all 34 image identities and found no remaining task containers.
