# Current-main dev34 baseline with DeepSeek Flash 1017

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
