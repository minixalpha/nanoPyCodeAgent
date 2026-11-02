# Six-task supplement for the official DeepSeek Harness

The six previously unscored tasks were rerun on **November 1, 2026** after the
maintainer requested fresh attempts. The supplement produced **four passes, two scored failures, and zero unscored errors**.
All six model executions completed normally, and every official verifier finished on its first attempt.

The original [34-task experiment](deepseek-harness-dev34-20261030.md) remains
**22 passes, six failures, and six unscored errors**. These six attempts are a
separate, outcome-selected development supplement. Using the 28 original accepted attempts plus these six new attempts gives descriptive mixed coverage of **26 passes, eight failures, and no remaining unscored tasks across 34 tasks**. They are not an
independent benchmark or a best-of-two score, and do not establish a causal
harness improvement. The original six scored failures were not rerun.

The [audited results](../../results/deepseek-harness-dev6-supplement-20261101.json)
retain every new trial, native reward/exception, analytical outcome, official
test count, timing, usage, and evidence hash. The
[v2 registration](../../configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json)
and [configuration history](../../configs/deepseek-harness-dev6-supplement-20261101/README.md)
record the changes made before model work. All six new outputs were
[frozen](../../configs/deepseek-harness-dev6-supplement-20261101/outputs-freeze.json)
at **2026-11-01 16:56:07.773103 UTC**, before reviewing new trajectories or hidden assertions;
**590 files** were rehashed. Raw logs remain local.

## Per-task results

All six had analytical score `null` in the original experiment. `—` denotes an
unscored outcome or no model execution. Pi values retain its historical audit;
`‡` marks its pipeline pass with public reference-test/solution exposure.

| Task | Original unscored cause | Pi audited | New raw | New audited | Official passed / failed | Agent seconds |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| multi-source-data-merger | Verifier: pyarrow download failed | 1 | 1 | Passed | 3 / 0 | 29.6 |
| pytorch-model-cli | Setup: uv installer TLS error | 0 | 0 | Failed | 5 / 1 | 628.4 |
| pytorch-model-recovery | Setup: 1,800-second timeout | 1 | 1 | Passed | 5 / 0 | 110.1 |
| query-optimize | Execution: terminal API transport error | 0 | 1 | Passed | 6 / 0 | 270.5 |
| torch-pipeline-parallelism ‡ | Verifier: CUDA dependency download failed | 1 | 0 | Failed | 2 / 2 | 632.4 |
| torch-tensor-parallelism | Verifier: timeout, then torch download failed | 1 | 1 | Passed | 13 / 0 | 73.4 |

- **pytorch-model-cli**: Completed normally. Five official checks passed; test_cli_tool_output failed because 14 of 50 tested MNIST predictions differed from the fixed expected values (image 0: 7, expected 2). Artifacts and executable checks passed. This is a scored assertion failure, not a dependency or verifier error.
- **torch-pipeline-parallelism**: Completed normally. Existence and no-hooks checks passed; both world-size cases failed backward-value comparisons at microbatch 0. World size 1: rank 0 lm_head.bwd max difference 0.04166729375720024. World size 2: rank 0 model.layers.1.bwd max difference 0.01778167486190796. The worker exceptions carry these official assertions, not verifier infrastructure errors.

These are official findings, not exhaustive root-cause proofs.

The six accepted evaluations ran **37 official cases: 34 passed, three failed, zero errors/skips**. Agent self-tests are not included. Native rewards and standard summaries are preserved; an official
zero is not automatically a valid scored failure. Setup errors, terminal API
errors, and verifier dependency/errors stay separate. A native agent timeout
can be scored only when its stop boundary is confirmed and official tests
complete successfully as an evaluation. Here, all **six completion boundaries** were confirmed, with **zero events after agent end or at/after verifier start**, **zero agent timeouts**, and **zero extra verifier attempts**.

## Preparation failures and verified transport

The initial direct-download preparation used `UV_HTTP_TIMEOUT=120`. Three
installation-only trials passed: data merger, PyTorch CLI, and query
optimization. Model recovery reached its **1,800-second setup timeout** in
verifier dependencies. The controller stopped after that completed second pair,
before the final pair or any model job. No active trial was interrupted. The
[initial evidence](../../configs/deepseek-harness-dev6-supplement-20261101/preflight-v1-evidence.json)
retains all four actual trials. Across the six selected tasks: **three passed,
one setup failure, two not started, zero model executions**. The initial model queue was superseded, never run.

A reusable optional PyPI wheel sidecar was added before v2 registration. It
forwards current original PyPI index metadata while preserving versions,
requirements, yanks, hashes, and extra-index settings. A wheel is served only
after matching current original release filename, size, SHA256, and HTTPS
origin and verifying the complete downloaded bytes. Cross-process locks protect
shared downloads; unavailable metadata and corrupt cache entries fail closed.
Source distributions and original extra indexes bypass this wheel cache.

V2 sets `UV_DEFAULT_INDEX=http://127.0.0.1:18744/simple` and
`UV_HTTP_TIMEOUT=600`, allowing a cold wheel to finish verification before any
body is served. Setup stays **1,800 seconds**. Original APT sources and verified
APT-index/uv/Python-release transports remain unchanged. No task image, package
pin, official test, or native agent/verifier limit was changed. Package caches
and new dependency preparation can affect runtime; this is not an isolated test
of model behavior or download transport.

All **six fresh v2 installation-only checks passed before any model job**,
including SDK initialization, Linux supervision, and exact-revision dependency
profiles. Five profiles were added; model recovery retains its existing one.
They preserve original Python/package/index requirements and run only
`pytest --version` from `/tmp`, without executing task code or assertions.
[Preflight evidence](../../configs/deepseek-harness-dev6-supplement-20261101/preflight-evidence.json)
and [launch registration](../../configs/deepseek-harness-dev6-supplement-20261101/launch-evidence.json)
precede model work. All six formal jobs repeated and passed the same dependency profiles. CLI setup took **1,690.4 seconds**, within the unchanged 1,800-second limit; a passed earlier preflight did not eliminate later download latency.

The full Harbor suite passed **301 tests**, including **16 wheel-cache contracts**.
A real original **uv 0.9.5** transport smoke with a fresh temporary uv cache also
passed, with **zero model calls**; [probe records](../../configs/deepseek-harness-dev6-supplement-20261101/transport-v2/transport-probes.json)
preserve both smoke versions and a verified range-download experiment.
The frozen transport log contains **675 original release-metadata events and 270 verified wheel responses: 224 cache hits, 46 cold responses, and 53 unique artifacts**, across **12 sidecars**, with **zero recorded transport errors**. Every wheel response has matching earlier original-release metadata in that sidecar.

## Preserved model configuration and audit

| Property | Value |
| --- | --- |
| Upstream | `deepseek-ai/deepseek-harness` `0.2.2-alpha.2`, source `f3803c96974ad4a94195fb97e5c637e9c2a3afe3` |
| Profile | `sdk-minimal`; same offline SDK/runtime distribution as the original run |
| Model/API | `deepseek/deepseek-flash`, high reasoning, `https://api.deepseek.com/anthropic` |
| Generation | Native prompt/tools/compaction/request retries; temperature and SDK max_tokens unset; native ceiling 256,000 |
| Adapter | Shared frozen source `eff073b1601435305155cad92b6ee9e2250fbbdc` |
| Transport source | `dc32b26194a06e7b070c5e8876d26ea0fcf3a7d3`; registered file hashes checked |
| Limits | Agent 900 seconds each; verifier 900 seconds, except query 1,800; setup 1,800 |
| Scheduling | Original relative order; concurrency two with pair barriers; one new formal attempt per task, no automatic whole-trial retry |
| Verifier retry | Only timeouts, at most three total attempts on unchanged output and original per-attempt limit |

The only frozen adapter change from the original source is reviewed dependency
preflight in `bootstrap.py`; the model driver, prompt integration, supervisor,
and verifier are byte-identical. The user's upstream checkout remains untouched.
Fresh isolated sessions receive no previous output, diagnosis, solution, or
personal configuration. The remaining **55 tasks stay unopened**. No SDK
service-lifecycle fix is included; the original KV/PyPI failures remain intact.

The official [agent integration guide](https://api-docs.deepseek.com/quick_start/agent_integrations/)
checked November 1 still maps the alias to DeepSeek-V4.1-Flash-1017, as recorded
in the [alias evidence](../../configs/deepseek-harness-dev6-supplement-20261101/model-alias-check.json).
It is mutable and does not prove the same backend checkpoint across dates.
Pi used OpenAI-compatible transport and a 384,000-token ceiling. Its sampler/WAL
scores have invalid/unverified legacy boundaries, and its pipeline pass has the
reference-exposure qualification. On this selected six-task subset, Harness and Pi each passed **four**; Harness gained query optimization and lost pipeline parallelism, with the Pi exposure qualification retained. On the **32 common accepted tasks** in the mixed coverage, Harness passed **25**, Pi **26**. Gains are DNA assembly and query optimization; losses are KV, PyPI, and pipeline parallelism. The KV/PyPI lifecycle and Pi pipeline exposure caveats apply to those losses.

After freezing, **98 recorded tool calls** were scanned and **three candidates with paired outputs** reviewed: two CLI calls accessed public MNIST data, and one pipeline call inspected the root/Python paths and environment. No benchmark reference tests/solution were observed in those records. The inspected environment contained no sensitive-named credential entries, and exact matching found the authorized provider key in **zero of 590 frozen files**. This targeted audit is not an exhaustive proof of no exposure or
exfiltration. Known SDK usage is **1,298,682 input tokens**, including **1,242,112 cached tokens**, and **79,429 output tokens**. All six trials report `usage_is_partial=false`; cost remains unknown. Cache tokens are included in input, not added again;
these are SDK usage subtotals, and no provider bill was queried.
The formal queue ran from **2026-11-01 15:50:21.232772 UTC** to **16:55:21.072680 UTC**: **3,899.8 seconds** of wall time and **1,744.3 summed agent seconds**. Queue time includes setup, verification and pair barriers, but excludes earlier preflights and transport probes.

```text
v2 plan SHA256: 69eb8272f3fcd125e062387f7f725c80f12b56b8a622d6a616d23f8e0e174a93
freeze SHA256: ee6a3c6a4f57b6da2ffcc04e81e54e888949285054aff8e7a218ce0f330671f3
results SHA256: 412a0d0acd266d5573ff722a2e5376ab0264b457821d0d603cf8b3f0e663d067
preflight evidence SHA256: e973e6d280171287c8c60b7888834b56259f897aac67e8ffa6c23daad39e3e06
original results SHA256: e94ca1e201d032617e9d4649f2cbfbb60127c1257e7a0f3b2696fea808288396
source archive SHA256: 0a851c705c243519cc573d077d8cf23295591498825d82b795b43b37255d43e4
distribution SHA256: d8f6157c880dfa5ae65b6c176dd86b1e32f5f31709f8f29fa7170db45d2fb9d6
runtime SHA256: 28e1eaeac3c594d2ce74c67c4f1e179c58ccf3d4dbb8c0faa719bec5745805f2
wheel-cache source SHA256: ced6bd7c1bf2b6ac1964c39d057708ba0e52c37c61a609651c49105ea145ea74
wheel audit SHA256: ef8385be4d1387b72014dca1e89b1281fed347714f9bd3e5f9e050b501e7366a
```

## Reproduction

Use the shared frozen adapter checkout and registered local artifacts. The
orchestrator invokes the standard `python -m harbor_adapter run --config ...`
entry point; it does not create per-job adapter copies. The published configs
retain local absolute paths, so reproduce with equivalent pinned artifacts and
new job names. Do not overwrite or replay the registered jobs.

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/dsh-harbor-venv"
export UV_CACHE_DIR="$PWD/.cache/uv"
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json \
  --phase preflight
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev6-supplement-20261101/experiment-v2.json \
  --phase model
```

Supply the authorized provider key only through the process environment.
English and Simplified Chinese reports contain the same results, caveats,
tables, identifiers, commands, and hashes.
