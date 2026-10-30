# Pi + DeepSeek Flash: 34-task development baseline

All **34 tasks received one fresh model attempt** and finished on October 29,
2026. The audited outcomes are **26 official passes, six scored failures, and
two unscored legacy timeout attempts**. One of the 26 passes followed confirmed
agent cancellation at its time limit; another retrieved public reference tests
and a solution. This run does **not** establish a complete, uncontaminated
34-task pass rate.

The unchanged standard summaries contain 25 ordinary passes, six ordinary
failures, and three `AgentTimeoutError` execution errors. Native raw rewards are
26 ones and eight zeros. The audit accepts the supervised Caffe timeout's raw
one and leaves the two legacy timeout zeros analytically null. It never
rewrites exceptions, changes native rewards, or replaces model outputs.

The [audited results](../../results/pi-deepseek-flash-dev34-20261024.json) contain
all trial IDs, source/task/configuration provenance, raw and analytical outcomes,
official test counts, usage, timing, audit flags, and evidence hashes. The
[v7 registration](../../configs/pi-deepseek-flash-dev34-20261024/experiment-v7.json) preserves the six original
attempts and registers the remaining 28 under corrected process supervision.
All outputs were hashed at **2026-10-30 13:54:30.827662 UTC**, before new solution
trajectory or hidden-test-content review; the
[freeze manifest](../../configs/pi-deepseek-flash-dev34-20261024/outputs-freeze.json) covers **1,449 files**.

## Agent, model, and protocol

| Property | Value |
| --- | --- |
| Pool | The exact October 12 development selection: 34 tasks with identical task revisions; the remaining 55 packages stayed unopened |
| Agent | Unmodified upstream Pi 1.4.0 local binary distribution; all files and permissions pinned; upstream archive checksum not independently verified |
| Model | `deepseek/deepseek-flash`, official `https://api.deepseek.com` OpenAI-compatible endpoint |
| Alias | Official documentation checked October 24 and 27 mapped it to DeepSeek-V4.1-Flash-1017; mutable alias, not an immutable checkpoint |
| Reasoning and sampling | `high`; temperature unset |
| Agent behavior | Stock prompt, tools, compaction, and request retry behavior; personal settings, extensions, skills, history, and other providers excluded |
| Model metadata | Context 1,000,000; output ceiling 384,000; native Pi generation behavior |
| Limits | Original task-native agent timeout and resources; separate 1,800-second setup limit |
| Queue | Ascending native timeout then name; consecutive pair barriers; concurrency two; one output per task |
| Verifier | Original official scripts and per-attempt limits; timeout-only retries permitted up to three attempts on the same output; zero used |
| Installation | Original 34 checks passed; 28 additional checks/probes passed after the supervision amendment |

QEMU's registered `qemu-alpine-ssh-v1` dependency profile passed under both
sources. The other 33 task profiles explicitly remain `not_configured`;
installation success does not certify unsupported verifier dependencies.
Verified caches preserve original package names, sizes, SHA256 digests, sources,
and task images. Original image identities and repository digests were verified
before each batch. Only newly introduced image references were evicted without
force; protected images and nine older stopped recovery containers were retained.

```text
plan SHA256: d90107ed15e47981fb3a09e74eb5d3b0e4f72acc96b30308c6d66ec28151128c
freeze SHA256: 76b775d898bbb84b21f80eee1061806d7d949465f9eef60dcab6dedeb326734b
results SHA256: b85d3bf2b0ea9661940f0e6b08e3bea71b2c41ae34da5c89f9ecd5197c6c8ff5
selection SHA256: 4572b1cc432a16b9c5d1dd554c8d2189ae80414f386a90bf03829bc4d0c3da85
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
first six adapter source: d6ed70a5d6a1c5b0f9b6c9d20b4a1c2b49153f67
remaining 28 adapter source: 29db8d7abbbe5f1660b8fb4d7caeeb0d183dc64d
```

The historical Nano baseline used 100 replies, a 65,536-token output request,
native timeout minus 180 seconds for work, an Anthropic-compatible endpoint, and
unset reasoning effort. Pi used its native loop, the full task-native timeout,
an OpenAI-compatible endpoint, and `high` reasoning. Different dates, a mutable
model alias, and these protocol differences prevent a causal agent-quality or
checkpoint comparison. There was no agent/prompt optimization between tasks.

## Process-supervision amendment and timeout accounting

The first six attempts used `d6ed70a`. Three passed and one failed normally.
`adaptive-rejection-sampler` and `db-wal-recovery` timed out. Operational
timestamps exposed Pi activity during sampler verification, so the controller
stopped at the completed-pair boundary before task seven. The 28 unstarted
tasks moved to `29db8d7` after **225 Harbor tests**, a network-disabled Docker
cancellation probe, and 28 fresh installation/supervisor checks. Pi bytes,
model settings, prompt/tools, task order/revisions, and budgets were unchanged.
See the [configuration history](../../configs/pi-deepseek-flash-dev34-20261024/README.md),
[original-six evidence](../../configs/pi-deepseek-flash-dev34-20261024/model-prefix-evidence.json),
[timeout evidence](../../configs/pi-deepseek-flash-dev34-20261024/timeout-boundary-evidence.json), and
[Docker probe](../../configs/pi-deepseek-flash-dev34-20261024/process-supervision-probe-evidence.json).

- **Sampler:** 40 message metadata records occurred after the reported agent
  end, including during verification. The verifier also encountered an APT lock
  and a `scipy==1.16.2` download timeout; official pytest never started. Its raw
  zero has both an invalid frozen boundary and a verifier dependency error.
- **WAL recovery:** no post-end message was observed, but the original adapter
  never acknowledged process stoppage. Official tests reported missing
  `/app/recovered.json` (0 passed, 7 failed). The raw zero remains unscored
  because the timeout boundary is unverified.
- **Caffe:** the corrected adapter reached the native 3,600-second agent limit,
  acknowledged cancellation with **13 stopped processes**, and then ran the
  official verifier. All **six tests passed**. The native `AgentTimeoutError`
  and standard `execution_error` summary remain; the analytical score is one.
  No post-end or post-verifier-start message was recorded.

All 28 corrected-source runs had completed or confirmed-cancelled supervision
records before official grading. The required guard rejects missing or
incomplete records. Successful solution servers may remain running by design;
cancellation stops detached agent tools as well. This amendment does not
retroactively validate the first two timeout attempts. There were **zero model
setup errors, zero whole-trial retries, and zero verifier retries**. The sampler
dependency error overlaps its invalid-boundary exclusion; it is not a third
unscored task.

## Per-task outcomes

| Task | Previous Nano raw | Pi raw | Audited outcome | Official tests passed / failed | Agent seconds |
| --- | ---: | ---: | --- | ---: | ---: |
| adaptive-rejection-sampler | 0 | 0 | Unscored: invalid boundary + verifier error | Not started | 901.3 |
| build-cython-ext | 1 | 1 | Passed | 11 / 0 | 834.2 |
| cancel-async-tasks | 1 | 0 | Failed | 5 / 1 | 104.8 |
| cobol-modernization | 1 | 1 | Passed | 3 / 0 | 430.2 |
| db-wal-recovery | 0 | 0 | Unscored: unverified timeout boundary | 0 / 7 | 898.7 |
| fix-code-vulnerability | 1 | 1 | Passed | 6 / 0 | 28.2 |
| git-multibranch | 1 | 1 | Passed | 1 / 0 | 80.5 |
| kv-store-grpc | 0 | 1 | Passed | 7 / 0 | 36.1 |
| log-summary-date-ranges | 1 | 0 | Failed | 1 / 1 | 13.9 |
| merge-diff-arc-agi-task | 1 | 1 | Passed | 5 / 0 | 77.1 |
| model-extraction-relu-logits | 1 | 0 | Failed | 0 / 1 | 177.0 |
| multi-source-data-merger | 1 | 1 | Passed | 3 / 0 | 34.3 |
| nginx-request-logging | 1 | 1 | Passed | 8 / 0 | 52.1 |
| openssl-selfsigned-cert | 1 | 1 | Passed | 6 / 0 | 16.5 |
| pypi-server | 1 | 1 | Passed | 1 / 0 | 70.3 |
| pytorch-model-cli | 1 | 0 | Failed | 5 / 1 | 660.7 |
| pytorch-model-recovery | 1 | 1 | Passed | 5 / 0 | 178.3 |
| qemu-alpine-ssh | 1 | 1 | Passed | 1 / 0 | 654.9 |
| query-optimize | 0 | 0 | Failed | 5 / 1 | 318.0 |
| regex-log | 1 | 1 | Passed | 1 / 0 | 157.0 |
| torch-pipeline-parallelism † | 0 | 1 | Passed | 4 / 0 | 562.2 |
| torch-tensor-parallelism | 1 | 1 | Passed | 13 / 0 | 90.8 |
| write-compressor | 1 | 1 | Passed | 3 / 0 | 304.1 |
| constraints-scheduling | 1 | 1 | Passed | 3 / 0 | 23.0 |
| custom-memory-heap-crash | 1 | 1 | Passed | 6 / 0 | 96.2 |
| dna-assembly | 1 | 0 | Failed | 0 / 1 | 763.3 |
| llm-inference-batching-scheduler | 1 | 1 | Passed | 6 / 0 | 337.7 |
| path-tracing | 1 | 1 | Passed | 5 / 0 | 133.1 |
| schemelike-metacircular-eval | 1 | 1 | Passed | 1 / 0 | 800.1 |
| caffe-cifar-10 | 1 | 1 | Timeout; confirmed stop, passed | 6 / 0 | 3600.4 |
| circuit-fibsqrt | 1 | 1 | Passed | 3 / 0 | 239.0 |
| mteb-leaderboard | 1 | 1 | Passed | 2 / 0 | 667.7 |
| regex-chess | 0 | 1 | Passed | 4 / 0 | 1618.2 |
| build-pov-ray | 1 | 1 | Passed | 3 / 0 | 267.4 |

† `torch-pipeline-parallelism` accessed public Terminal-Bench tests and a
reference solution. Its official pass is retained and flagged below.
Test counts use the final official pytest summary, preserving parameterized
cases: pipeline has four cases and tensor parallelism 13; native CTRF summaries
deduplicate these to three each. The 32 accepted evaluations executed **139
official cases: 133 passed, six failed, zero errors/skips**. The unscored WAL
trial's seven failed cases are separate. Embedded upstream/self-test counts
are not added to the final official wrapper totals.

The six valid failures were:

| Task | Official failure evidence |
| --- | --- |
| cancel-async-tasks | Excess tasks missed cleanup messages: 0 instead of 2 |
| log-summary-date-ranges | Month-to-date ERROR count 14160 instead of 4682 |
| model-extraction-relu-logits | Recovered matrix failed to match row 24 |
| pytorch-model-cli | CLI predictions differed from expected values |
| query-optimize | Runtime 0.8657636019925121 seconds exceeded 1.05 × 0.6539265539904591 seconds |
| dna-assembly | Primer melting temperatures differed by 5.4112089999999995 degrees C, above the 5-degree limit |

These are official assertion findings, not proofs of complete root causes.
Against the [October 12 Nano baseline](dev34-main-baseline-20261012.md), three
previous failures now have official passes: `kv-store-grpc`,
`torch-pipeline-parallelism` (exposure flagged), and `regex-chess`. Five previous
passes now fail: `cancel-async-tasks`, `log-summary-date-ranges`,
`model-extraction-relu-logits`, `pytorch-model-cli`, and `dna-assembly`.
Sampler and WAL remain unresolved. Historical Nano's 28/34 is not directly
comparable to a complete new Pi rate, which this run does not supply.

## Exposure and private artifacts

After freezing outputs, a targeted scan reviewed **925 recorded tool starts**
and matching tool outputs for benchmark repositories, hidden paths, and
environment access. `torch-pipeline-parallelism` downloaded upstream
`tests/test_outputs.py` (178 lines), `solution/solve.sh` (112 lines), and
`instruction.md` (33 lines) from public repository `harbor-framework/terminal-bench-2`,
read the reference solution, and ran the downloaded tests. The remote `main`
was not pinned to the registered package revision. Its pass does not establish
unaided task completion. WAL and Git listed `/logs/verifier` while it was empty;
those listing outputs contained no official tests. MTEB application sources,
public results, and the Scandinavian leaderboard were consulted for that task,
separately from Terminal-Bench reference material.

WAL and `llm-inference-batching-scheduler` printed environment variables that
included the configured DeepSeek API key. An exact-match scan found the key in
**four local raw files**, the event and native-session files for those two tasks.
The key value and raw traces are not published. Rotate that key before another
experiment. Published artifacts contain derived findings and hashes only.
This targeted audit is not proof that every other exposure or exfiltration
channel was absent. The pool was already exposed development material.

## Timing, usage, and reproduction

Model jobs ran from **2026-10-29 13:54:04.318461 UTC** to
**2026-10-29 19:11:52.019151 UTC**: **317.8 minutes**, including pair barriers,
verification, and the supervision-amendment gap. Summed agent execution was
**15,227.44641 seconds**. All controllers and task containers exited; older
stopped recovery containers were preserved.

Recorded usage totals **27,164,763 input tokens** (including **26,331,264 cached
tokens**) and **718,414 output tokens**. The known peak-rate cost subtotal is
approximately **$1.270134084**. All three interrupted trials have partial usage
and cost coverage; the old adapter's false completeness flags remain raw and
are corrected only in derived audit fields. In-flight or later legacy activity
can be missing. These are known subtotals, not a complete token count or a
reconciled bill; registered pricing also excludes off-peak discounts.

The registered controller was invoked from the experiment worktree with the
key supplied only through the environment. It delegates each job to the
standard Harbor entry point from its corresponding frozen checkout:

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/harbor-supervised-runtime-venv"
uv run --frozen --project jobs/supervised-source/benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev34-20261024/experiment-v7.json \
  --phase all
```

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>
```

Completed records are skipped; started-but-unfinished records refuse replay.
The final v7 plan validated. All 34 source snapshots, task revisions, public
model configurations, and distribution pins matched; pair barriers and
preflight gates passed. All 1,449 frozen file hashes were rechecked during
audit. Native artifacts remain in ignored `jobs/runtime-source/jobs/` and
`jobs/supervised-source/jobs/`; reports and audited JSON are the shareable
baseline record. A complete English/Simplified Chinese report pair is maintained
in the same change.

## Post-run workflow review

Four reproducible workflow defects were corrected after this run: zero-exit
model-loading warnings could hide fallback settings; multiple Pi configurations
could overwrite one job-local snapshot; failed streams with initialized zero
usage could be labeled complete after a successful retry; and concurrent first
publication of a shared distribution could abort one preparation. Regression
tests reproduced nine failures against the evaluated corrected source, while
the updated full Harbor suite passed **238 tests**. The pinned Pi 1.4.0 offline
probe accepted the registered configuration and rejected an invalid `maxTokens`
configuration despite its zero exit code, without a model call.

The [review evidence](../../configs/pi-deepseek-flash-dev34-20261024/review-fixes-evidence.json)
records the fixes and archive checks. Each archived model job had one Pi agent
and the registered valid public model configuration; no model-loading warning
or failed zero-usage assistant event was found in the checked job logs/events.
All 1,449 frozen file hashes still match. The original evaluated sources,
exceptions, usage, outcomes, and result JSON remain unchanged; these workflow
fixes apply to future runs and do not imply that this baseline was rerun.
