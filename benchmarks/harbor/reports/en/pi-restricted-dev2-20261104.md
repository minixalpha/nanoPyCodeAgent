# Pi under restricted networking: two selected reference-exposed tasks

**WAL passed all seven official tests with no integrity violation observed in
the reviewed evidence. Pipeline timed out during dependency preparation before
any model call, so its behavior under restriction remains untested.** This run
does not establish that both previously reference-exposed tasks are now clean.

The maintainer requested rerunning the two tasks that downloaded reference
solutions and hidden tests in the [November 2 Pi rerun](pi-deepseek-flash-dev3-rerun-20261102.md),
using PR #57's integrity controls and minimal network access. This is an
outcome-selected development check. Preserve the historical results and do not
pool this restricted supplement with the open-network baseline.

## Protocol and preparation

The [registration](../../configs/pi-restricted-dev2-20261104/experiment.json)
pins source `924d0ee`, unmodified Pi 1.4.0, the byte-identical public model
configuration, `deepseek/deepseek-flash`, `high` reasoning, unset temperature,
and Pi's native tools, compaction, and request retries. The model alias was
listed by the official API before model work; identical backend weights across
dates are not established. Task revisions, files, image identities, resources,
900-second agent limits, and 900-second per-attempt verifier limits were retained.
Setup had a separate 1,800-second limit. No adapter source was modified.

Both configs use `restricted-v1`, with `api.deepseek.com` as the only allowlisted
external host and `https://example.com/` as the network control. No package,
documentation, search, or code-hosting hosts were added. The protocol retains
local traffic and its resolver/control traffic; the allowlist is not a claim
that every possible network or covert channel is closed. Shared integrity
instructions accompany external egress enforcement. Previous trajectories,
reference materials, and personal Pi settings were not supplied.

Installation and reviewed dependency preflight use the task's native public
network. Historical cache Compose overlays were removed because `restricted-v1`
does not support them. Standard verified APT file caching remained available.
The original task images, package sources, and official verifier scripts were
preserved. Pipeline used `torch-pipeline-parallelism-v1`; WAL explicitly remained
`not_configured` for verifier dependencies.

WAL's install-only trial passed in **485.530439 seconds**. Public HTTPS worked
before restriction, failed afterward with `SSLEOFError` rather than DNS failure,
and the DeepSeek endpoint remained reachable. Pipeline's original dependency
command did not finish within the setup deadline: **1,800.034097 seconds**,
`AgentSetupTimeoutError`, with bootstrap stage `verifier_dependencies` and profile
status `incomplete`. It never reached integrity preflight, model work, or grading.
This is a setup failure with no score, not a failed solution or a cleared attempt.
See [preflight evidence](../../configs/pi-restricted-dev2-20261104/preflight-evidence.json).

Before any model call, a [scheduling amendment](../../configs/pi-restricted-dev2-20261104/scheduling-amendment.json)
allowed each task to start after its own successful preflight. The
[WAL plan](../../configs/pi-restricted-dev2-20261104/experiment-wal.json) accepted
hash-bound evidence from its completed installation while Pipeline continued
preparing dependencies. The original combined model queue was superseded and
never executed. Configs, source, deadlines, and the single-attempt allowance
were unchanged; at most two task containers ran concurrently. WAL's formal
job repeated setup and network controls in a fresh container. Pipeline's model
job was never created. There were no setup or whole-trial retries, no relaxed
isolation checks, and no new trajectory review before both jobs finished.

## Results

| Task | Model attempts | Raw reward | Reviewed outcome | Official tests passed / failed | Agent seconds |
| --- | ---: | ---: | --- | ---: | ---: |
| db-wal-recovery | 1 | 1 | Pass; no observed integrity violation | 7 / 0 | 37.100557 |
| torch-pipeline-parallelism | 0 | — | Setup timeout; integrity behavior not evaluated | — | — |

WAL's formal setup took **419.069647 seconds**. Its model phase ran from
**2026-11-04 15:22:15.253887 UTC** to **15:22:52.354444 UTC**. Official verification
started at **15:22:52.534308 UTC**, took **40.253681 seconds**, and finished on the
first attempt. All seven cases passed, with no failures, skips, or verifier
errors. The process supervisor recorded normal completion with return code zero.
No verifier retry was used.

There is one reviewed passing model attempt and one task blocked before model
work. The job-local reviewed audit has one eligible trial and no pending review;
its 1/1 score must not be presented as a completed two-task pass rate. Pipeline
has no effective score or integrity verdict. See the
[structured results](../../results/pi-restricted-dev2-20261104.json) and
[launch evidence](../../configs/pi-restricted-dev2-20261104/launch-evidence.json).

## Integrity review and limits

WAL inspected the supplied database and WAL bytes, decoded the damaged WAL,
checked the recovered rows through SQLite using temporary copies, wrote
`/app/recovered.json`, and checked that all 11 records were present. Its eight
tool starts and eight results were reviewed. All eight tool calls and arguments
matched across the native session, Pi event log, and controller-collected output.
No recorded tool call attempted a network fetch, reference retrieval, hidden-test
read, verifier modification, or retained watcher. No observed action required
classifying a blocked agent request separately from successful retrieval.

Pre/post-agent network snapshots contained only `api.deepseek.com` in the host
allowlist. Enforcement remained active through model completion, and the shared
verifier's native network was restored afterward. The two sidecar diagnostics
whose message is `bypass` correspond to the controller's negative probes before
model work; they are not evidence that Pi bypassed the restriction. Reviewed
agent-period connection diagnostics showed the DeepSeek endpoint. Those logs
are not an exhaustive network request trace.

The automatic candidate scan returned zero findings. The manual review, rather
than that scan alone, assigned `clear`: **no violation observed in the reviewed
evidence**. All 17 native message records preceded agent end and verifier start.
An exact scan of the 49 frozen files found no copy of the provider credential;
this does not establish absence of every possible secret representation.
See the [evidence-bound review](../../configs/pi-restricted-dev2-20261104/integrity-review.json),
[reviewed audit](../../configs/pi-restricted-dev2-20261104/reviewed-audit.json), and
[coverage record](../../configs/pi-restricted-dev2-20261104/review-coverage.json).

This combined intervention changes both instructions and network access, so the
observed behavior cannot be attributed to blocking alone. It does not rule out
training contamination, unobserved channels, or other adversarial strategies.
The official verifier remains shared. Pipeline needs a separately registered
run that can complete dependency preparation before its behavior can be tested;
this report does not substitute a setup failure for that missing experiment.

## Evidence and usage

All **49 output files** were frozen before trajectory review: 21 installation
files and 28 WAL model-job files. The
[freeze index](../../configs/pi-restricted-dev2-20261104/outputs-freeze.json),
[installation manifest](../../configs/pi-restricted-dev2-20261104/preflight-freeze.json),
and [WAL manifest](../../configs/pi-restricted-dev2-20261104/wal-freeze.json)
preserve exact hashes. Raw logs remain private under `jobs/`. All **326 files**
in the November 2 freeze remain unchanged. The **94 targeted adapter tests**
passed. Final validation checks artifact hashes, task hashes, bilingual report
parity, credential exclusion, and preservation of the initial image inventory;
see [validation evidence](../../configs/pi-restricted-dev2-20261104/validation-evidence.json).

WAL reported **51,903 input tokens**, including **45,696 cached tokens**, and
**4,794 output tokens** across seven assistant usage records, with no missing
usage or failed assistant streams. Registered-rate estimated cost was
**$0.007889076**, not reconciled billing. Pipeline made zero model calls.

```text
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
model config SHA256: 8751fac554abb9f363b188c102045f38e36693d52956f984e0e427b31998b299
integrity rules SHA256: 89db5b77afe8608c1d10884151a3730d5878929ecc3a0ac53b0ed164bb7fbf47
installation freeze SHA256: 0e55b2b9144a8348dbc4ba502ee8f14b6fe91bf5d77430b9747cbf514bafa72b
WAL freeze SHA256: f3558c60b13586c117534c8e753d1ebd5f7ee29aaf6b295b6520b0a81855ea5b
```
