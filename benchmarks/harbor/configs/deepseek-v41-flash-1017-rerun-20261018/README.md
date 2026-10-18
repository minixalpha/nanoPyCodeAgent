# DeepSeek Flash 1017: rerun the six previous failures

**Completed:** three passes, one scored failure, and two unscored verifier
dependency-download errors. See the
[final report](../../reports/deepseek-v41-flash-1017-rerun-20261018.md) and
[audited results](../../results/deepseek-v41-flash-1017-rerun-20261018.json).
The sampler and pipeline native zeros are retained as raw evidence; their
analytical scores are null because official tests never started.

This experiment selects all six failed tasks from the latest
[34-task baseline](../../reports/dev34-main-baseline-20261012.md):
`adaptive-rejection-sampler`, `db-wal-recovery`, `kv-store-grpc`,
`query-optimize`, `torch-pipeline-parallelism`, and `regex-chess`.
The [selection](selection.json) binds the previous result file and trial IDs.

The [final registered plan](experiment-v2.json) runs each task once with
`deepseek/deepseek-flash` against the official DeepSeek Anthropic-compatible
endpoint. On October 18, 2026, DeepSeek's
[API documentation](https://api-docs.deepseek.com/quick_start/agent_integrations/)
states that `deepseek-flash` serves **DeepSeek-V4.1-Flash-1017**; see also the
[October 17 announcement](https://api-docs.deepseek.com/news/news261017/).
The API alias is not an immutable checkpoint pin.

## Matched conditions

- Agent and adapter: the original unchanged checkout at
  `2eb99b608dfb39464d17d109a4a8f11afda607a9`, located at
  `jobs/dev34-baseline-main-source`.
- Prompt: the original [385-word headless prompt](main-prompt.txt).
- Tasks: original pinned revisions, complete file hashes, resources, and
  [image identities](image-digests.json), verified against the previous run.
- Limits: 100 replies, 65,536 output tokens per request, and the native agent
  timeout minus 180 seconds. That gives 720 seconds for five tasks and 3420
  seconds for regex chess. Setup has a separate 1800-second limit.
- Queue: ascending work budget, then task name; consecutive pairs complete
  before the next pair starts, with concurrency two.
- Transport: the previous v5 dependency-cache composition, including verified
  original APT indexes and uv/Python release archives, plus the identical
  original CPython archive described below. Images, package sources, official
  tests, and native verifier limits remain unchanged.
- Attempts: one fresh model trial per task, no whole-trial retries or
  outcome-based replacements. Only verifier timeouts may retry, up to three
  attempts with the same model output and original per-attempt limit.

## Execution and evidence

The existing `benchmarks/harbor/scripts/run_comparison.py` validates the plan and
invokes the standard `uv run --project benchmarks/harbor python -m harbor_adapter
run --config ...` entry point from the frozen source checkout. Run its
`--phase preflight` before `--phase model` with this experiment's plan.
Credentials come from the environment and must not be committed.

Fresh install-only checks cover all six tasks before model work. All six
verifier dependency profiles are **`not_configured`**: successful agent
installation does not certify their verifier dependencies. Full trials repeat
setup in fresh containers. Installation failures and verifier errors are
reported separately from scored failures.

The orchestration records live under
`jobs/deepseek-v41-flash-1017-rerun-20261018-v2-orchestration/`; native inputs,
source snapshots, logs, and results live under the frozen source checkout's
`jobs/flash1017-*-20261018{,-input}/` directories. Raw logs and trajectories
remain local because they can contain credentials. Only derived results and
evidence hashes belong in version control.

Freeze every model output before reviewing new trajectories or official test
contents. Previous failure diagnoses and solutions are not supplied to the
model. This is an exposed development pool selected for previous failure;
one new trial per task cannot isolate a checkpoint effect, establish
reliability, or provide a fresh score for the entire 34-task pool.

## Pre-model transport amendment

The [original plan](experiment.json) started two installation-only trials.
Both downloaded CPython 3.13.9+20251120, which uv selected normally but which
was absent from the previous cache registration. Transfers from the original
GitHub URL progressed slowly. Before any model work, both installation trials
were administratively interrupted; their native `CancelledError` results and
the intervention record remain local. The other four original installation
trials had not started.

The existing release-cache utility fetched and verified the same original
archive using public GitHub release metadata: **34,257,108 bytes**, SHA256
`1bc9a94ab2425fb6ae58e45f69cab61647759b57895649701390822d976fa923`.
The [additional manifest](python-agent-release-manifest.json),
[combined manifest](dependency-release-manifest.json), and
[v2 composition](transport-v2/dependency-cache.compose.json) register this cache
hit. The final plan binds their hashes and repeats all six installation checks
afresh. Python selection, archive contents, source code, tasks, resources,
budgets, and model queue are unchanged. No scored model trial was interrupted
or retried.
