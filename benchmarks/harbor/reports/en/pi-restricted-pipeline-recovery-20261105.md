# Restricted Pi Pipeline: dependency recovery and an unscored model run

**Dependency preparation is fixed: the final preflight took 205.670052 seconds,
and the fresh formal container completed setup in 142.791023 seconds. Pipeline
still has no official score.** Pi finished its solution, but Harbor's output
collector rejected a long final JSON event before the official verifier started.
That separate collector bug is now fixed and tested; the failed run is preserved.

This follows the [November 4 restricted check](pi-restricted-dev2-20261104.md),
where WAL passed all seven official tests and Pipeline hit its 1,800-second setup
limit before any model call. This selected development supplement does not
replace that report or the historical open-network baseline.

## Preparation and preserved failures

The [first recovery registration](../../configs/pi-restricted-pipeline-recovery-20261105/experiment.json)
pinned source `8e42c62` and added a managed, verified PyPI wheel cache. Its
installation-only trial passed, but the fresh formal container encountered a
different download failure: the unchanged uv installer received
`curl: (18) Transferred a partial file` from the original uv release URL.
No model call occurred in that failed container.

The [second registration](../../configs/pi-restricted-pipeline-recovery-v2-20261105/experiment.json)
pinned source `a867883` and also enabled the existing verified original uv/Python
archive cache. Original release metadata was fetched again before registration;
archive filename, size, and SHA256 were checked. The original uv `0.9.5` and
Python `3.13.9` archives were retained, including Python build `20251014`.
The original installer scripts and uv's Python selection were unchanged.

| Attempt | Setup seconds | Model attempts | Outcome |
| --- | ---: | ---: | --- |
| November 4 Pipeline installation | 1800.034097 | 0 | Setup timeout; preserved |
| Recovery 1 installation-only | 212.639386 | 0 | Passed |
| Recovery 1 formal container | 370.463495 | 0 | Truncated uv download; preserved |
| Recovery 2 installation-only | 205.670052 | 0 | Passed |
| Recovery 2 formal container | 142.791023 | 1 | Setup passed; collector failed after model completion |

The formal model attempt contains 25 assistant usage records.

Recovery 1 served **45 wheels / 3,080,594,478 bytes**, with **44 cache hits** and
one fresh download. Recovery 2's preflight and formal setup each served all
**45 wheels** from verified cache and both original release archives without a
redirect. Every wheel matched current PyPI release metadata. These elapsed times
are operational observations across different containers, not a controlled
speedup estimate. See the [first preflight](../../configs/pi-restricted-pipeline-recovery-20261105/preflight-evidence.json),
[uv failure](../../configs/pi-restricted-pipeline-recovery-20261105/failed-model-setup-evidence.json),
and [second preflight](../../configs/pi-restricted-pipeline-recovery-v2-20261105/preflight-evidence.json).

## Network and cache boundaries

The opt-in `pypi-verified-v1` transport uses the same preparation path for all
supported agents. A controller-owned helper serves dependency setup and official
verification only. Its scripts and optional release manifest are snapshotted and
hashed; its original-release cache is read-only. The helper has one CPU and
512 MiB, separate from the unchanged task resources. No host directory is
mounted into the task container.

The helper and its loopback listener were removed before network preflight and
checked again before model work. Only `api.deepseek.com` was allowlisted during
the model phase. Original task bytes, image identity, package sources, shared
integrity instructions, 1,800-second setup limit, 900-second model limit, and
900-second per-verifier-attempt limit were preserved. Installation and official
verification retain native public networking. The model's network allowlist was
never widened, and the official verifier remains shared.

Pi `1.4.0`, `deepseek/deepseek-flash`, `high` reasoning, unset temperature, and
the public model configuration were retained. This mutable model alias does not
establish identical backend weights across dates. WAL was not rerun and did not
use this new dependency transport; no matched two-task causal comparison is
claimed.

## Collector failure and integrity observations

The formal model phase lasted **433.014135 seconds**. Native Pi output contains
`agent_settled`, its final assistant stop reason is `stop`, and process supervision
records successful completion. Harbor's line-oriented callback reader then
raised `ValueError: Separator is not found, and chunk exceed the limit` while
reading the **209,940-byte** `agent_end` event against a **65,536-byte** limit.
The official verifier never started: raw reward, effective score, and scored
integrity verdict are all absent. See [model evidence](../../configs/pi-restricted-pipeline-recovery-v2-20261105/model-evidence.json).

All **35 tool starts and 35 results** were examined. Tool arguments matched
across the native session, event log, and controller output. The controller's
327 events are the exact prefix of the native log's 329 events; only `agent_end`
and `agent_settled` are missing. All 62 native message records precede the
recorded agent-phase end. Pi read installed Transformers source, wrote
`/app/pipeline_parallel.py`, developed and removed a temporary local self-test,
and inspected its final file.

No recorded tool call fetched an external answer, obtained official hidden-test
contents, changed verifier controls, or left an observed watcher. However, Pi
also performed broad local test-file searches, enumerated `/logs`, read its
current supervisor PID record, and searched dependency caches for the task
function name. Those searches returned library files or current agent metadata;
the task-function search found no match. This is not a blanket certification
that no benchmark hunting was attempted. The zero-finding candidate scan is not
proof of clean behavior. See [review coverage](../../configs/pi-restricted-pipeline-recovery-v2-20261105/review-coverage.json).

Pre/post network snapshots retained the API-only allowlist. The two egress
diagnostics saying `bypass` correspond to controller negative probes before
model work. Agent-period named connection diagnostics show the DeepSeek endpoint;
they are not an exhaustive request trace. An environment dump copied the API
credential into three private frozen logs. Raw logs remain private; no credential
value or raw trajectory is published.

The [automatic audit](../../configs/pi-restricted-pipeline-recovery-v2-20261105/unscored-audit.json)
reports an unscored `integrity_error` because the complete agent/verifier
enforcement sequence is absent. That status is not an agent-cheating verdict.
No scored `clear` or `violation` review was assigned to this infrastructure error.
Training contamination and unobserved channels remain outside the review's claims.

## Fix, validation, and evidence

Source `1b6e3dc` changes the restricted collector to UTF-8-aware chunked reads,
preserving exact output, command deadlines, stdin handling, cancellation, and
process cleanup. **410 Harbor tests passed**; the **3** explicitly enabled
Docker tests also passed, including a **300,000-byte** UTF-8 line and cache
absence during restricted model work. See [implementation validation](../../configs/pi-restricted-pipeline-recovery-v2-20261105/implementation-validation.json).

A [replay of the frozen native event log](../../configs/pi-restricted-pipeline-recovery-v2-20261105/native-event-replay.json)
reproduced the original collector error and confirmed that the fixed collector
preserves the entire output exactly. This check made no model call.

All **71 files** from the four completed recovery jobs were frozen before model
trajectory review. The [freeze index](../../configs/pi-restricted-pipeline-recovery-v2-20261105/outputs-freeze.json)
binds all four manifests. The prior **49** restricted-run files and **326**
November 2 files remain unchanged. [Structured results](../../results/pi-restricted-pipeline-recovery-20261105.json)
retain all setup errors and the missing official score. Final checks are recorded
in [validation evidence](../../configs/pi-restricted-pipeline-recovery-v2-20261105/validation-evidence.json).

Pi reported **667,185 input tokens**, including **639,872 cached tokens**, and
**24,996 output tokens**, with 25 usage records and none missing. Estimated cost
was **$0.042028332**, not reconciled billing. There were no assistant API errors.

No additional model attempt was launched after this error. The repository's
[retry rule](../../../../AGENTS.md) permits only verifier-timeout retries, so an
additional model attempt requires an explicit maintainer exception. The fixed
collector has been validated with model-free tests; Pipeline's official outcome
remains unresolved.

```text
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
model config SHA256: 8751fac554abb9f363b188c102045f38e36693d52956f984e0e427b31998b299
Recovery 2 release manifest SHA256: 3a132b29494bea24ec2c872a9b9c88dda059575a0bb9f2d869f9ff1c50810edb
Recovery 2 model freeze SHA256: 7597e12251e688623cd7de611404650cc5dba063b5f4eccba6c2117ea640d24d
```
