# Flash 1017: authorized retry of the two unscored tasks

**The sampler passed; pipeline parallelism failed.** Both now have valid
official test results in this follow-up. The sampler completed on its first
verification attempt. Pipeline verification timed out during dependency
preparation on its first attempt, then completed on its second attempt with a
valid failure score. No third attempt was needed or started.

| Task | Official result | Tests passed / failed | Verifier attempts | Agent seconds |
| --- | --- | ---: | --- | ---: |
| adaptive-rejection-sampler | Passed, reward 1 | 9 / 0 | 1: completed | 591.4 |
| torch-pipeline-parallelism | Failed, reward 0 | 2 / 2 | 1: timeout; 2: completed | 562.6 |

The [initial six-trial run](deepseek-v41-flash-1017-rerun-20261018.md) left both
tasks unscored because official dependencies failed to download. The user then
authorized retrying these two tasks with a maximum of three attempts. The
original containers had been deleted and their artifact manifests held no
`/app` outputs, so this follow-up generated **one fresh model output per task**.
It does not regrade or prove correctness of the original unscored submissions.
Those results and frozen artifacts remain unchanged.

The [registered plan](../../configs/deepseek-v41-flash-1017-recovery-20261018/experiment.json)
has SHA256
`7ba0d4083cbc856a364417bc51025a8bd84434eb39319927664bfb4c018fba9d`.
The [audited results](../../results/deepseek-v41-flash-1017-recovery-20261018.json)
retain trial IDs, all verifier attempts, actual pytest and native CTRF counts,
source and wheel hashes, preserved-output hashes, authorization, and preflight
and exposure findings. The
[configuration README](../../configs/deepseek-v41-flash-1017-recovery-20261018/README.md)
documents execution and local evidence paths.

Both fresh model trials used `deepseek/deepseek-flash` against the official
DeepSeek endpoint. Agent Python sources are byte-identical to the initial
evaluation, with the same 385-word prompt, pinned task revisions, original
images, resources, and limits: 100 replies, 65,536 output tokens per reply,
720 seconds of model work, and separate 1800-second setup. The evaluated
checkout is frozen at `35fe1a2d6a786619a2adace1cfa9d0acca08d533`; its adapter
adds optional pre-test uv network-download recovery. The user-authorized plan
enables it explicitly. Ordinary runs still use the default timeout-only policy.

The standard Harbor entry point ran two fresh installation-only checks before
model work. Both succeeded, while both verifier dependency profiles remained
explicitly **`not_configured`**. Installation success was not treated as verifier
dependency certification. The model then ran once per task. Verification reused
each fresh output and container, with at most three total attempts and the
original **900-second per-attempt limit**. Valid official results, including
zero, stop recovery immediately; setup failures and verifier errors remain
separate from scored failures. Original package sources and test scripts were
unchanged.

The sampler installed R, submitted `ars.R`, and passed all nine official tests,
including distribution sampling, sample files, modularity, input validation,
and non-log-concavity handling. Verification took about 38.3 seconds, with
8.55 seconds in pytest. It required no retry.

Pipeline's first attempt reached its 900-second limit while uv was downloading
PyTorch/CUDA dependencies; pytest had not started. The second attempt reused
the same container and cache, finished dependency installation, and executed
all four official cases. The existence and no-hooks checks passed. Both
world-size cases failed the backward-signal comparison at **`lm_head.bwd`,
microbatch 0**: rank 0 for world size 1 and rank 1 for world size 2, each with
maximum difference **0.03571479767560959**. The agent reported successful
self-checks on its own CPU PyTorch/Transformers stack, but these did not
establish compliance with the official comparison. This is a valid scored
failure, not a verifier installation error. Native CTRF deduplicates the
parameterized cases into three test names; actual pytest execution was
**two passed and two failed**. Both representations are retained.

Pipeline's second attempt took 828.9 seconds, including 76.46 seconds in pytest.
The retry budget was therefore respected: one native timeout retry, no
whole-trial retries, and no attempt beyond the valid failure. The optional
dependency-download-error rule did not trigger in these native trials; its
behavior is covered by regression tests.

All outputs froze at **2026-10-18 15:06:01 UTC**, after both trials ended and
before new trajectory or official-test-content review. Thirteen official
pytest cases executed: 11 passed and two failed, with no skips or errors.
Both `/app` artifact collections succeeded, preserving submitted code and
sample files locally for future inspection or verification. Compact artifact
tree digests and exact submitted-code/sample hashes are recorded in the results.
All original image identities were unchanged and trial containers were removed.
A review of both frozen trajectories found no observed benchmark-answer
retrieval, hidden verifier content, or provider credentials. Pipeline listed
an empty verifier-log directory and inspected its own bootstrap/startup logs;
other network accesses concerned public dependency sources.

The retry implementation passed all **178 Harbor workflow tests**, including
bounded retries, archival, exhausted errors remaining unscored, default behavior,
and stopping on valid results. The implementation's three CI checks passed.
The English and Chinese adapter READMEs both document the optional mode.

Model jobs occupied about **39.4 minutes** of wall time, excluding preflight.
This remains an exploratory follow-up on previously exposed tasks with fresh
model outputs and live dependency resolution. It does not isolate a checkpoint
effect or provide a fresh score for the full 34-task pool. Raw trajectories,
logs, and `/app` contents remain local; only derived findings and hashes are
published.
