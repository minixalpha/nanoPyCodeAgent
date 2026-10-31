# Official DeepSeek Harness on Pi's 34-task development pool

All **34 registered jobs finished on October 31, 2026**: **22 official passes,
six scored failures, and six unscored errors**. There were 32 model executions;
two jobs failed during setup. Two scored failures have a confirmed SDK service
lifecycle caveat. These results describe the official Harness's `sdk-minimal`
configuration through its Python SDK, not every Harness interface or a complete
34-task pass rate.

On the **26 tasks with accepted scores in both runs**, this configuration passed
**21**, versus **22** for [Pi](pi-deepseek-flash-dev34-20261024.md).
`dna-assembly` changed from failure to pass; `kv-store-grpc` and `pypi-server`
changed from pass to failure. Both regressions involve services available during
agent self-tests but absent during verification. A separate keyless probe
confirmed that normal SDK closure stops a background server. This comparison
does not establish a causal difference in model or harness capability.

The [audited results](../../results/deepseek-harness-dev34-20261030.json) retain
all 34 trial IDs, raw and analytical outcomes, official test counts, timing,
usage, diagnoses, and evidence hashes. The
[registration](../../configs/deepseek-harness-dev34-20261030/experiment.json)
and [configuration history](../../configs/deepseek-harness-dev34-20261030/README.md)
preserve preparation and execution decisions. All outputs were frozen at
**2026-10-31 15:47:11.582274 UTC**, before new solution trajectories or hidden
test contents were reviewed. The
[freeze manifest](../../configs/deepseek-harness-dev34-20261030/outputs-freeze.json)
covers **2,506 files**, all rehashed during audit. Raw traces remain local.

## Configuration and preserved protocol

| Property | Value |
| --- | --- |
| Pool | Exact existing Pi selection of 34 development tasks, unchanged revisions, task files, images, resources, and official tests; the other 55 tasks remained unopened |
| Agent | Official `deepseek-ai/deepseek-harness`, version `0.2.2-alpha.2`, source `f3803c96974ad4a94195fb97e5c637e9c2a3afe3` |
| Profile | Upstream benchmark-recommended `sdk-minimal`, driven through the public Python SDK |
| Behavior | Native system prompt, persistent bash, image reading, working-directory tool, compaction, request retries, and generation defaults; fresh home/session per task |
| Isolation | No personal instructions, skills, extensions, settings, or prior sessions; task tools execute inside the task container |
| Model | `deepseek/deepseek-flash`, `high` reasoning, official Messages endpoint `https://api.deepseek.com/anthropic` |
| Generation | Temperature and SDK `max_tokens` unset; upstream output ceiling 256,000 |
| Adapter | Frozen source `5b503ab6d04af2f6a719ec0dbe5418bfad4bf128` in `jobs/deepseek-harness-runtime-source` |
| Limits | Native task agent/verifier timeouts and resources; setup limit 1,800 seconds |
| Queue | Same Pi order; concurrency two with consecutive pair barriers; no whole-trial retries |
| Verification | Original scripts and per-attempt limits; only verifier timeouts may retry, at most three total attempts on the same agent output |

The official [agent integration guide](https://api-docs.deepseek.com/quick_start/agent_integrations/)
checked October 30 and 31 maps `deepseek-flash` to DeepSeek-V4.1-Flash-1017;
the [alias record](../../configs/deepseek-harness-dev34-20261030/model-alias-check.json)
records the later check. This remains a mutable alias, not proof of an identical
backend checkpoint across dates. Pi used its native OpenAI-compatible endpoint
and a 384,000-token ceiling. Neither run imposed Nano's 100-reply limit or
finalization reminders. These endpoint, budget, date, and lifecycle differences
make this a comparison of complete configurations.

The user's original upstream checkout remained clean and unchanged. An isolated
copy was built with the upstream frozen pnpm lockfile (Node 26.7.0, pnpm 11.28.5).
All eight artifact-build gates and the official keyless SDK smoke passed.
The offline distribution contains the SDK, native runtime, and five dependency
wheels. Source bytes, distribution bytes and file modes are pinned.

```text
plan SHA256: fb59d5618c44e691babb80b2ea8323eb45edf9f45383e61344d747b870bc6d6e
freeze SHA256: cc421c1429450ac41d355d0df8333f4ab10ca4da0bf47f24bc3892d0724d9c24
results SHA256: e94ca1e201d032617e9d4649f2cbfbb60127c1257e7a0f3b2696fea808288396
selection SHA256: 4572b1cc432a16b9c5d1dd554c8d2189ae80414f386a90bf03829bc4d0c3da85
source archive SHA256: 0a851c705c243519cc573d077d8cf23295591498825d82b795b43b37255d43e4
distribution SHA256: d8f6157c880dfa5ae65b6c176dd86b1e32f5f31709f8f29fa7170db45d2fb9d6
runtime SHA256: 28e1eaeac3c594d2ce74c67c4f1e179c58ccf3d4dbb8c0faa719bec5745805f2
lifecycle diagnostic SHA256: 4257a96a3415a7d389fb7b3fb10f819341714ba833b0911eb2a6468171e70c47
```

## Installation, execution boundaries, and error accounting

All **34 installation-only checks passed before the first model job**, including
SDK initialization and Linux supervisor probes. QEMU's `qemu-alpine-ssh-v1`
and model recovery's `pytorch-model-recovery-v1` dependency profiles passed;
the other **32 profiles are explicitly `not_configured`**. The
[pre-model metadata amendment](../../configs/deepseek-harness-dev34-20261030/profile-metadata-amendment.json)
corrected a historical description of the profile count without changing any
execution setting. The [preflight evidence](../../configs/deepseek-harness-dev34-20261030/preflight-evidence.json)
does not guarantee that later network-dependent setup will succeed.

The first WAL installation smoke failed because the Python `dsh` launcher needs
an explicit `DSH_HOME` even for its version query. The adapter supplied an
isolated version-probe home before registration; the corrected smoke passed.
Both records remain in [setup evidence](../../configs/deepseek-harness-dev34-20261030/setup-evidence.json),
and neither is a scored model attempt. Validation included 280 Harbor tests
before that integration fix and 11 DeepSeek-focused tests after it. The final
full Harbor suite also passed all 280 tests. Its first invocation passed 273
and had seven local HTTP fixtures blocked by sandbox socket permissions; the
complete rerun with local sockets permitted passed in 17.56 seconds.

Every one of the **32 model executions** has a confirmed completion or
cancellation boundary before official verification. No recorded SDK event
occurred after agent end or at/after verifier start. The three agent timeouts
were sampler, model extraction, and pipeline parallelism, each with its native
900-second limit; cancellation stopped **10, 4, and 8 processes**, respectively.
Sampler and model extraction have accepted official failures. Pipeline has a
separate verifier dependency error and remains unscored.

Native rewards remain **22 ones, 10 zeros, and two nulls**. Unchanged standard
summaries contain **28 `scored`, four `execution_error`, and two `setup_failed`**
records. The analytical audit distinguishes official assertions from incomplete
setup, terminal API failure, and verifier errors; it does not rewrite native
exceptions or rewards.

| Unscored task | Category and evidence |
| --- | --- |
| pytorch-model-cli | Setup: original uv 0.9.11 installer fetch failed with curl 35 / `SSL_ERROR_SYSCALL` at `releases.astral.sh:443`; `NetworkConnectionError`, no model execution |
| pytorch-model-recovery | Setup: native `AgentSetupTimeoutError` after 1,800 seconds in `verifier_dependencies`; SDK/supervisor checks passed but this formal dependency check did not finish; no model execution |
| multi-source-data-merger | Verifier: `pyarrow==22.0.0` download/extraction timed out with `UV_HTTP_TIMEOUT=30`; official pytest never began |
| query-optimize | Execution: SDK `finish_reason=error`, terminal `TRANSPORT` error after six attempts of one provider request, including five native request retries; native `NonZeroAgentExitCodeError`; later official tests found missing SQL output |
| torch-pipeline-parallelism | Verifier: after confirmed agent timeout, download of `nvidia-cusolver-cu12==11.7.1.2` required by `torch==2.7.0` timed out; official pytest never began |
| torch-tensor-parallelism | Verifier: first attempt reached 900 seconds; second failed downloading `torch==2.7.0` with `UV_HTTP_TIMEOUT=30`; official pytest never began |

There were **three extra verifier attempts**: sampler timed out twice at 900
seconds, then its third attempt completed in 26.3 seconds; tensor parallelism
timed out once at 900 seconds, then its second attempt ended with the dependency
failure. These used the same outputs and original scripts. Dependency failures
did not trigger retries. No complete task, model output, or setup failure was
replayed. Native request retries within the agent are separate from these
verifier retries and from whole-trial retries.

## Per-task outcomes

`—` denotes no analytical score or no execution, as appropriate. Pi values are
its audited scores, not its raw rewards. `†` marks the service lifecycle caveat;
`‡` marks Pi's reference-exposed pipeline pass.

| Task | Pi audited | Harness raw | Harness audited outcome | Official tests passed / failed | Agent seconds |
| --- | ---: | ---: | --- | ---: | ---: |
| adaptive-rejection-sampler | — | 0 | Timeout; confirmed stop, failed | 4 / 5 | 899.4 |
| build-cython-ext | 1 | 1 | Passed | 11 / 0 | 593.1 |
| cancel-async-tasks | 0 | 0 | Failed | 5 / 1 | 26.3 |
| cobol-modernization | 1 | 1 | Passed | 3 / 0 | 172.4 |
| db-wal-recovery | — | 1 | Passed | 7 / 0 | 34.1 |
| fix-code-vulnerability | 1 | 1 | Passed | 6 / 0 | 42.1 |
| git-multibranch | 1 | 1 | Passed | 1 / 0 | 83.5 |
| kv-store-grpc † | 1 | 0 | Failed | 5 / 2 | 45.8 |
| log-summary-date-ranges | 0 | 0 | Failed | 1 / 1 | 21.0 |
| merge-diff-arc-agi-task | 1 | 1 | Passed | 5 / 0 | 110.5 |
| model-extraction-relu-logits | 0 | 0 | Timeout; confirmed stop, failed | 0 / 1 | 899.4 |
| multi-source-data-merger | 1 | 0 | Unscored: verifier error | — | 27.8 |
| nginx-request-logging | 1 | 1 | Passed | 8 / 0 | 138.0 |
| openssl-selfsigned-cert | 1 | 1 | Passed | 6 / 0 | 36.2 |
| pypi-server † | 1 | 0 | Failed | 0 / 1 | 40.2 |
| pytorch-model-cli | 0 | — | Unscored: setup error | — | — |
| pytorch-model-recovery | 1 | — | Unscored: setup error | — | — |
| qemu-alpine-ssh | 1 | 1 | Passed | 1 / 0 | 270.2 |
| query-optimize | 0 | 0 | Unscored: API error | 2 / 4 | 231.7 |
| regex-log | 1 | 1 | Passed | 1 / 0 | 90.3 |
| torch-pipeline-parallelism ‡ | 1 | 0 | Unscored: verifier error | — | 899.3 |
| torch-tensor-parallelism | 1 | 0 | Unscored: verifier error | — | 131.3 |
| write-compressor | 1 | 1 | Passed | 3 / 0 | 143.6 |
| constraints-scheduling | 1 | 1 | Passed | 3 / 0 | 24.3 |
| custom-memory-heap-crash | 1 | 1 | Passed | 6 / 0 | 131.7 |
| dna-assembly | 0 | 1 | Passed | 1 / 0 | 944.5 |
| llm-inference-batching-scheduler | 1 | 1 | Passed | 6 / 0 | 503.8 |
| path-tracing | 1 | 1 | Passed | 5 / 0 | 229.8 |
| schemelike-metacircular-eval | 1 | 1 | Passed | 1 / 0 | 902.8 |
| caffe-cifar-10 | 1 | 1 | Passed | 6 / 0 | 2200.5 |
| circuit-fibsqrt | 1 | 1 | Passed | 3 / 0 | 461.1 |
| mteb-leaderboard | 1 | 1 | Passed | 2 / 0 | 1172.2 |
| regex-chess | 1 | 1 | Passed | 4 / 0 | 1907.7 |
| build-pov-ray | 1 | 1 | Passed | 3 / 0 | 891.9 |

Counts come from the final official pytest summary, preserving parameterized
cases; agent self-tests and embedded upstream test runs are not added. The
**28 accepted evaluations** executed **118 cases: 107 passed, 11 failed, zero
errors/skips**. The API-interrupted, unscored query trial separately ran **two
passed and four failed** cases. The other five unscored trials never reached
official pytest.

| Scored failure | Official assertion or missing artifact |
| --- | --- |
| adaptive-rejection-sampler | `Rscript` and generated sample files missing after the confirmed timeout; installing R when absent is explicitly part of the task, so this is a task failure, not a verifier dependency exclusion |
| cancel-async-tasks | Excess-task cleanup messages: zero, expected two |
| kv-store-grpc † | Port 5328 not listening; connection refused |
| log-summary-date-ranges | Today ERROR count 74, expected 370 |
| model-extraction-relu-logits | `/app/stolen_A1.npy` missing after the confirmed timeout |
| pypi-server † | Installation of `vectorops==0.1.0` from `localhost:8080` failed with the local index unreachable |

These are official findings, not exhaustive root-cause proofs.

## SDK service lifecycle diagnostic

KV's agent successfully exercised `SetVal`/`GetVal` with value 123. PyPI's agent
started a `nohup` server, fetched the index, and installed and exercised the
package in a separate virtual environment. Both services were unavailable to
the official verifier after the SDK context had closed.

The pinned upstream SDK's normal shutdown disposes managed terminals and their
descendants. The shared Linux supervisor permits solution services after normal
completion, but that cannot preserve services already stopped by the SDK.
The post-freeze [diagnostic](../../configs/deepseek-harness-dev34-20261030/sdk-lifecycle-probe.json)
used the upstream keyless mock fixture and the exact pinned runtime, with **two
local mock requests and zero real model calls**. A `nohup` Python HTTP server
was **reachable before SDK close and unreachable after close**. The
[reusable probe](../../scripts/probe_deepseek_lifecycle.py) records its own,
fixture, and runtime hashes:

```bash
jobs/dsh-harbor-venv/bin/python benchmarks/harbor/scripts/probe_deepseek_lifecycle.py \
  --upstream-source jobs/deepseek-harness-build-f3803c9/source \
  --runtime jobs/deepseek-harness-build-f3803c9/source/dist-exe/deepseek-harness-sdk-runtime-linux-x64
```

This diagnostic was performed after all benchmark outputs were frozen. It
confirms a lifecycle limitation of the measured SDK integration, not that both
tasks would pass every official assertion under a different lifecycle. Both
zeros remain scored failures of this configuration. No lifecycle fix, server
restart, or regrading was applied to the registered run.

## Interpretation against Pi

Pi's audit records **26 passes, six failures, and two unscored legacy timeouts**.
Its sampler boundary was invalid and its WAL boundary unverified; its pipeline
pass accessed public reference tests and a solution. Those qualifications remain
in the [Pi report](pi-deepseek-flash-dev34-20261024.md).

The 26 common accepted tasks yield **Harness 21 / Pi 22** passes. The only gain
is `dna-assembly`; the two losses are `kv-store-grpc` and `pypi-server`, both
with the lifecycle caveat. `db-wal-recovery` passes here but was unscored for
Pi, so it is not a paired gain. Sampler now has a valid official failure but
also lacks a valid Pi comparison. The six new unscored tasks likewise cannot be
used to infer gains or losses. The common subset is determined by evaluability
and is not an unbiased replacement for the registered 34-task pool. There is
no statistically controlled ranking, complete paired pass rate, or claim that
the observed changes isolate the harness alone.

## Exposure, usage, timing, and reproducibility

After freezing outputs, a targeted scan covered **675 recorded tool calls**
and matching candidate outputs for benchmark repositories, hidden paths, and
environment access. No external Terminal-Bench reference retrieval or official
hidden-test access was observed in that scan. A calendar `PRODID` and a
task-provided C++ canary produced benign Terminal-Bench string matches. MTEB
downloaded public `embeddings-benchmark/results` application data at
`3125e8302256ac01d4dd68b6f92902b3e6a78987`; this is distinct from Terminal-Bench
tests or solutions. The development pool was already exposed historically;
the targeted scan does not prove complete absence of exposure or exfiltration.

An exact-byte scan of all **2,506 frozen files** found the authorized provider
credential in **zero files**. This is limited to that key and these files;
it does not alter the historical Pi credential findings. Raw trajectories and
credential values are not published. The maintainer's October 31 authorization
and model launch are recorded in [launch evidence](../../configs/deepseek-harness-dev34-20261030/launch-evidence.json).

| Known usage or timing | Value |
| --- | ---: |
| Input tokens, including cached input | 25,052,194 |
| Cached input tokens, already included above | 24,346,112 |
| Output tokens | 634,263 |
| Cost | Unknown |
| Summed agent execution seconds | 14,306.464573 |
| Queue wall seconds, including setup and verification | 16,984.894313 |
| First job start (UTC) | 2026-10-31 11:03:13.156046 |
| Last job finish (UTC) | 2026-10-31 15:46:18.050359 |

Usage is a **known subtotal**. Sampler, model extraction, query optimization,
pipeline parallelism, DNA assembly, and LLM batching have partial usage. Failed
native retries and interrupted requests can omit usage even when a later
completion succeeds. Do not add cached tokens to input again or infer a bill
from these records. Different network conditions, setup failures, verifier
retries, and accepted task sets prevent a controlled speed or cost comparison.

Final validation rechecked source/task/configuration hashes, all preflight-before-
model boundaries, every pair barrier, and **68 original image checks** across
preflight and formal jobs. Original package sources and task images were
preserved; cache hits required matching filename, size, and SHA256. Only newly
introduced image references were evicted without force, retaining protected
images. All 34 jobs finished and **zero task containers remained active**.

The [configuration README](../../configs/deepseek-harness-dev34-20261030/README.md)
contains the build and execution commands. Every job uses the standard
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`
entry point from the frozen source. Native evidence is retained under
`jobs/deepseek-harness-runtime-source/jobs/`, with orchestration and image events
under `jobs/deepseek-harness-dev34-20261030-orchestration/`. Published JSON and
hash manifests allow provenance inspection; reproducing from source also
requires the registered task packages, images, built distribution, and provider
access. Existing registered jobs refuse overwrite or replay.
