# Authorized six-task DeepSeek Harness supplement

Status: the [v2 registration](experiment-v2.json) adds verified PyPI wheel
transport after the initial preparation encountered a setup timeout. All six fresh v2
dependency checks passed. [Preflight evidence](preflight-evidence.json) and
[launch registration](launch-evidence.json) precede the six formal model jobs.
Formal execution is now registered; results will be audited after all outputs
are frozen.

The initial direct-download preflight passed data merger, PyTorch CLI, and query
optimization. Model recovery exceeded its 1,800-second setup limit while
preparing verifier dependencies. The controller stopped after that completed
second pair, before the third pair or any model job; no active trial was
interrupted. [Initial evidence](preflight-v1-evidence.json) preserves all four
trials. The original registration remains immutable; its model queue is
superseded, not executed.

The maintainer explicitly requested another run of the six tasks left
analytically unscored in the [original dev34 results](../../results/deepseek-harness-dev34-20261030.json).
This is a separate, outcome-selected development supplement. Keep the original
22 passes, six failures, and six unscored errors unchanged. Record every new
attempt separately, including preparation failures; never choose the better
of two scores or present the supplement as an independent clean benchmark.

The six selected tasks are `multi-source-data-merger`, `pytorch-model-cli`,
`pytorch-model-recovery`, `query-optimize`, `torch-pipeline-parallelism`, and
`torch-tensor-parallelism`, in their original relative order. Task revisions,
files, images, official test scripts, resources, and native time limits are
unchanged. The other 55 tasks remain unopened. Earlier failures and diagnostic
material are not included in model prompts.

The upstream Harness distribution is unchanged: source
`f3803c96974ad4a94195fb97e5c637e9c2a3afe3`, `sdk-minimal`, native prompt/tools,
compaction and request retries, `deepseek/deepseek-flash`, high reasoning,
Messages endpoint, temperature and SDK max_tokens unset. The official guide
checked on November 1 still documents DeepSeek-V4.1-Flash-1017 for this mutable
alias; this does not establish an identical backend checkpoint across dates.
No service-lifecycle change is included.

The frozen adapter source is `eff073b1601435305155cad92b6ee9e2250fbbdc`, at
`jobs/deepseek-harness-supplement-source`. Relative to the original experiment,
it adds reviewed dependency-only preflight profiles for the five previously
unsupported tasks in this subset. Model recovery retains its existing profile.
The commands preserve the original Python version, package pins, APT
requirements, and index options, and run only `pytest --version` from `/tmp`.
All 285 Harbor tests passed for the dependency-profile addition. The final
transport implementation passed all 301 Harbor tests, including 16 cache
contracts, and a real uv 0.9.5 smoke with a fresh temporary uv cache and zero
model calls. See [transport probes](transport-v2/transport-probes.json).

The initial plan set `UV_HTTP_TIMEOUT=120` instead of the default 30. V2 sets
`UV_DEFAULT_INDEX=http://127.0.0.1:18744/simple` and `UV_HTTP_TIMEOUT=600` to allow
a cold wheel to be fully verified before response bytes are served. The loopback
sidecar forwards current original PyPI metadata, preserving versions, hashes,
requirements, yanks, and extra-index settings. Original wheel bytes are checked
against current release filename, size, SHA256, and HTTPS origin on every
request; cache corruption or unavailable metadata fails closed. Cross-process
locks protect shared downloads. Public metadata/cache events persist in
`.cache/nanopy-harbor/pypi-ranges/audit/dsh-sup6-cache-20261101.jsonl`.
The existing verified APT-index and uv/Python-release caches remain identical.
These transport changes do not increase task-native agent/verifier limits. Setup remains 1,800
seconds; concurrency remains two with pair barriers. There is one fresh model
attempt per selected task and no automatic whole-trial retry. Only verifier
timeouts may retry, at most three total attempts on the same new output.

All six fresh install-only checks, including their reviewed dependency
profiles, must pass before model work. Every formal job repeats dependency
setup before calling the model. Failure at that point is a setup error, not a
scored failure. Preserve all new outputs, freeze them before reviewing new
trajectories or hidden assertions, and publish full English and Simplified
Chinese reports with original and supplemental outcomes distinguished.

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/dsh-harbor-venv"
export UV_CACHE_DIR="$PWD/.cache/uv"
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json \
  --phase preflight
# Supply the previously authorized DEEPSEEK_API_KEY in the environment.
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json \
  --phase model
```

Every job uses the standard `python -m harbor_adapter run --config ...` entry
point from the shared frozen source. Native outputs remain under
`jobs/deepseek-harness-supplement-source/jobs/`; orchestration and image events
remain under `jobs/deepseek-harness-dev6-supplement-20261101-v2-orchestration/`.
The existing original registration and frozen outputs are not overwritten.
