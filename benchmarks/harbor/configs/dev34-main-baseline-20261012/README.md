# Common-main baseline for the 34-task development pool

This run evaluates **all 34 existing development tasks once**, with fresh model
outputs from main `2eb99b608dfb39464d17d109a4a8f11afda607a9`. Both local main
and origin/main pointed to that commit when the run was registered. Earlier
pilot20, repeat experiments, and the twelve-task baseline remain separate;
none of their model outputs or rewards count toward this run.

**Completed:** 28/34 passed (82.35%), with six scored failures, zero model-phase
setup errors, zero verifier errors, and no verifier retries. See the
[final report](../../reports/en/dev34-main-baseline-20261012.md) and
[audited results](../../results/dev34-main-baseline-20261012.json).
One passing tensor-parallelism trial accessed external benchmark revision
metadata; its raw score is retained with a separate exposure flag.

[Selection](selection.json) is the union of the previously exercised 22 tasks
and the twelve additions. It uses the same pinned 89-task dataset revision.
The remaining 55 packages stay unopened. These are development tasks with prior
outcome and partial test/trace exposure, not a held-out evaluation.

## Frozen inputs

- [Original plan](experiment.json): runtime, task revisions, complete task-file hashes,
  prompt/configuration hashes, work budgets, preflight, and queue order.
- [Prompt](main-prompt.txt): current main's 385-word headless prompt.
- [Original images](image-digests.json): all 34 images were already cached;
  identities and repository digests are recorded before execution.
- Runtime worktree: `jobs/dev34-baseline-main-source`, detached at the exact
  main commit. The standard runner independently snapshots agent/adapter source
  and records installed-wheel hashes for every job.

Model: `deepseek/deepseek-flash`, official DeepSeek Anthropic-compatible endpoint,
100 replies, 65,536 output tokens per request. Temperature and reasoning effort
are unset. No prompt or agent optimization is included.

Work budget is each task's native agent timeout minus 180 seconds: 23 tasks at
720 seconds, one at 1,020, four at 1,620, one at 2,220, four at 3,420, and
POV-Ray at 11,820. Setup independently allows 1,800 seconds. Original task images,
resources, package sources, and official test scripts remain unchanged.

The model queue sorts by ascending work budget, then task name. Consecutive pairs
finish before the next pair starts; maximum concurrency is two. Every task gets
exactly one fresh model trial. There are no outcome-based replacements or retries
of entire model trials. Verifiers may retry **only timeouts**, at most three
total attempts, with the same agent output and original per-attempt limits.

## Run

The active model plan is [experiment-v5.json](experiment-v5.json). Before any
model call, the strict orchestrator validated exactly one successful native
installation per task: 29 from v3 and all five from v4. Task revisions, source
snapshots, wheel digests, bootstrap/profile states, and native artifact hashes
match the frozen main runtime. Earlier partial preflight plans are historical
evidence and must not be used to start model work. The original
install-only job ended with three setup timeouts, two uv-download TLS errors,
and one cancellation; 28 tasks never started. No models or official tests ran.
[Preserved evidence](preflight-v1-evidence.json) records the native artifacts
and their hashes. The amendment adds only an APT transport cache, keeping the
runtime source, original sources/images/scripts, budgets, and scoring fixed.

The v2 host-proxy route proved unreachable from Docker containers and was
stopped before model work. [Native evidence](preflight-v2-evidence.json) retains
the errors and the subsequent successful sidecar connectivity probe. Historical
v2 utility hashes refer to branch commit `f4cdab9`.

The third preflight completed 29 installations, with two truncated uv archive
downloads and one QEMU Python-download TLS error. Its two remaining installations
were interrupted before model work after the new archive-cache integration probe
passed. [Preserved cumulative evidence](preflight-before-v4-evidence.json)
includes native results and the separately identified administrative interruptions.
V4 successfully checked `log-summary-date-ranges`, `qemu-alpine-ssh`, `regex-log`,
`circuit-fibsqrt`, and `build-pov-ray`. QEMU's registered verifier dependency
profile passed; the other 33 tasks remain explicitly `not_configured`.

The [APT configuration](transport-v3/apt-cache.conf) routes only the named
public APT HTTP origins through a loopback proxy. Its
[Compose override](transport-v5/dependency-cache.compose.json) starts cache
sidecars in each task's own network namespace and waits for their health checks.
Each uses an already cached image pinned by digest, has no task filesystem or
agent credentials mounted, publishes no ports, and has a separate 0.5 CPU /
256 MiB limit. Task resources stay unchanged. The APT sidecar shares the verified
host index cache, protected by per-digest cross-process locks. No host proxy
process is required.

The APT configuration is mounted read-only. Mutable release metadata and
packages are not proxy-cached; immutable SHA256 indexes require complete hash
verification. Model/API traffic retains its normal route.
The recorded real-network probe fetched the original 8,790,396-byte Debian
index in 138.418 seconds cold and 0.008 seconds warm, with identical SHA256.

The archive sidecar serves only original files bound to the
[release manifest](dependency-release-manifest-v5.json): uv 0.9.11, uv 0.9.5,
CPython 3.13.9 from build 20251014, and CPython 3.14.0 from build 20251120.
The latter is listed by the original uv 0.9.11 download index and was warmed
before model work, after a long managed-Python installation was observed.
It adds a verified cache hit to the original-source fallback without changing
Python version selection. Filename, size, and full SHA256 must match the
original public release metadata. Its cache and manifest mounts are read-only.
The unchanged installers use their supported `UV_INSTALLER_GITHUB_BASE_URL` and
`UV_PYTHON_INSTALL_MIRROR` transport settings. Python version selection stays
unchanged; uncached versions redirect to their original GitHub URLs. The
[uv](uv-cache-integration-probe.json) and
[Python/pytest](python-cache-integration-probe.json) probes executed no models
or task assertions. All transport files, utilities, and the release manifest
are frozen by hashes in v5. Every model task uses this same final transport.

From the repository root, with credentials in the process environment, set
`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic` and leave
`ANTHROPIC_MODEL` unset. Do not put credentials in configuration or published
artifacts. Raw traces can contain environment values and require review/redaction
before sharing.

```bash
python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev34-main-baseline-20261012/experiment-v5.json \
  --phase preflight

python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev34-main-baseline-20261012/experiment-v5.json \
  --phase model
```

The orchestrator calls only the standard
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`
entry point from the frozen repository root. The v5 preflight command validates
the accepted native records instead of replaying installation trials. Fresh
successful installations exist for all 34 tasks before model work. Only QEMU has a reviewed verifier dependency
profile, `qemu-alpine-ssh-v1`; the other 33 remain explicitly `not_configured`.
Agent installation success does not certify unsupported verifier dependencies.

If installation infrastructure fails, preserve the failed job and register any
amendment before model work. Reuse a successful native install-only record only
after the existing orchestrator verifies complete task/source/wheel/bootstrap/
configuration provenance. Never synthesize a successful job or reinterpret a
setup failure as an agent correctness failure.

Keep all scored failures, setup errors, verifier errors, and incomplete usage
records. A native zero without executed assertions is a verifier error in the
analysis, while its raw reward remains unchanged. Inspect operational stage and
completion metadata while running; defer new trajectory and hidden-test content
review until all new model outputs freeze. Audit external benchmark-answer
exposure separately from raw scores.

For reproduction, use new job names and a new registration directory. Existing
jobs and their immutable registration must not be overwritten.
