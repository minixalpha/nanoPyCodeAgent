# Authorized retry of the two unscored Flash 1017 tasks

**Completed:** sampler passed all nine official tests on the first verification;
pipeline failed two of four cases on the second verification after its first
attempt timed out during dependency preparation. No third attempt was started.
See the [report](../../reports/en/deepseek-v41-flash-1017-recovery-20261018.md) and
[audited results](../../results/deepseek-v41-flash-1017-recovery-20261018.json).

The user requested another attempt on `adaptive-rejection-sampler` and
`torch-pipeline-parallelism`, with at most three attempts. The initial
[six-trial run](../../reports/en/deepseek-v41-flash-1017-rerun-20261018.md) left
these two tasks unscored because verifier dependencies failed to download.
The original containers were deleted and their artifact manifests contain no
`/app` outputs, so this is a **new model trial per task**, not a regrade of the
original submissions. All original results and evidence remain unchanged.

The [registered plan](experiment.json) uses the standard Harbor entry point
from the unchanged checkout `jobs/flash1017-recovery-source`, frozen at
`35fe1a2d6a786619a2adace1cfa9d0acca08d533`. Agent Python source hashes exactly
match the original agent. Only the adapter changes: its optional
`retry_dependency_errors=true` verifier setting is enabled for this authorized
recovery experiment. It remains disabled by default.

Each task receives one fresh `deepseek/deepseek-flash` trial with the same
prompt, pinned task revision, original image, resources, and budgets as before:
100 replies, 65,536 output tokens per reply, a 720-second work budget, and
separate 1800-second setup. No whole-trial retries are permitted.

The verifier runs the original test script at most **three times total**,
including its first attempt in this follow-up. Each attempt retains the task's
original 900-second time limit. It may retry native verifier timeouts and
recognized uv network download failures before pytest starts. Any official
test result, including failure, stops the retries. A CTRF report, pytest
execution output, or successful reward prevents download-error recovery.
Unrelated errors are not retried. All attempts reuse the same fresh model
output and container, preserve logs, and clear stale canonical rewards.
Exhausted download errors remain unscored and raise `VerifierDependencyError`.
Complete `/app` artifacts are collected for future inspection or verification.

Both tasks receive fresh install-only preflight before model work. Their
verifier dependency profiles remain explicitly `not_configured`; successful
agent installation is not verifier dependency certification. The same verified
APT and original uv/Python release caches are used. No task image, package
source, official test script, or native per-attempt limit changes.

The existing `benchmarks/harbor/scripts/run_comparison.py` runs
`--phase preflight` before `--phase model` with this plan. Native jobs live under
the frozen source checkout's `jobs/flash1017-recovery-*-20261018{,-input}/`
directories. Orchestration records live at
`jobs/flash1017-recovery-orchestration/`. Freeze both outputs before reviewing
new trajectories or official test contents. Raw logs, trajectories, and `/app`
artifacts remain local; publish derived findings and hashes only.

The retry implementation passed all **178 Harbor workflow tests**, including
real subprocess checks that dependency failures are opt-in, bounded, archived,
and never confused with executed test failures or successful rewards. The
bilingual adapter README documents the option. These tasks are already exposed
development tasks; this follow-up does not establish checkpoint causality or a
new score for the entire 34-task pool.
