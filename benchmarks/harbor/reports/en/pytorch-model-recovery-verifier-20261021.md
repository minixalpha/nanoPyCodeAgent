# PyTorch model recovery: retained-solution verifier continuation

Date: 2026-10-21. This separately authorized batch retries the existing
`pytorch-model-recovery__nCs7Y4H` solution from the
[October 20 supplement](dev34-flash1017-recovery-20261020.md).

**All three additional verifier attempts timed out before pytest started. The
score remains `null`: this is a verifier error, with no scored pass or failure.**
No model was called and no new solution was generated. This solution has now
received six verifier attempts across two separately recorded batches.

| Batch attempt | Attempt on this solution | Result | Duration | Last observed stage |
| --- | --- | --- | --- | --- |
| 1 | 4 | Timeout; unscored | 900.002 s | PyTorch/CUDA downloads |
| 2 | 5 | Timeout; unscored | 900.002 s | Torch download after CUDA dependencies completed |
| 3 | 6 | Timeout; unscored | 900.002 s | Torch download; completed dependencies reused |

The new verifier execution time was approximately 45 minutes. No attempt
produced a CTRF test report or valid reward. New model calls and model cost were
both zero. The original dev34 baseline remains **26 passes, five scored
failures, three unscored verifier errors**. Neither that baseline nor the
October 20 supplement was rewritten, and no composite dev34 score is reported.

## Policy and preserved identity

The batch used the repository's reusable `verify-retained` command, the same
Docker container, the same `/app` solution, the original test scripts and package
sources, and the task's native 900-second per-attempt limit. The separately
authorized budget was at most three additional attempts, with opt-in dependency
download and collection recovery. Any completed valid score, including zero,
would have stopped the batch. Whole-trial retries and model calls were disabled.

The original solution used core agent commit
`ce28b1e826a292d796ba64f13e79199b66f65758` and runtime commit
`40fdd041c370a96dc06f86b436eacc01ce1566d7`. Its recorded model identity is
DeepSeek-V4.1-Flash-1017 through the mutable `deepseek-flash` alias; this batch
makes no new claim about the alias's current mapping. The frozen solution
`/app/model.pt` SHA256 remains
`098642cbf41010a7fab7a9cf32995b49300cc3ccb1d724e7d57d729330f0bb4e`.

No fresh agent setup or dependency preflight was run. This task has no registered
verifier dependency profile; one is not claimed to have passed.

## Storage and execution observations

The first attempt briefly reported APT cache proxy connection refusals during
service startup, used existing indexes and installed curl, then entered the
original uv downloads. Both sidecars were healthy for the later attempts.
The published host command now waits for service health checks. The actual
executed source snapshot is archived; this hardening did not change the running
attempt runner, time limits, solution, or retry policy.

To prevent disk exhaustion, 50 duplicate image-cache files totaling
1,576,934,879 bytes were temporarily relocated and subsequently restored with
SHA256 verification. Separately, 37 abandoned partial-download directories
totaling 5,753,708,793 bytes were archived after checking timestamps, open file
handles, and hashes. Their archives remain under the two dated
`/tmp/nanopy-pytorch-recovery-20261021-stale-downloads*` directories. Active
downloads, completed dependency caches, original Docker images, and task files
were not changed by this maintenance.

## Evidence and validation

The original trial files were restored byte for byte. Frozen solution and test
hashes passed checks before and after verification. All three original project
containers are stopped and retained, with unchanged container and image
identities and no container OOM flag. The local Harbor suite passed **203 tests**,
including log restoration, cancellation, service readiness, and valid-zero
handling.

- [Machine-readable result](../../results/pytorch-model-recovery-verifier-20261021.json)
- [Registered continuation plan](../../configs/pytorch-model-recovery-verifier-20261021.json)
- Local raw evidence: `jobs/pytorch-model-recovery-verifier-20261021/`, including
  registration, executed sources, every attempt's logs, integrity checks,
  container retention, storage history, and partial-download archive manifests.
- [Complete Simplified Chinese version](../zh-CN/pytorch-model-recovery-verifier-20261021.md)
