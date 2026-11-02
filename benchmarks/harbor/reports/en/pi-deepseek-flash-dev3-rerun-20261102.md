# Pi + DeepSeek Flash: authorized three-task rerun

**All three fresh attempts finished: two official passes and one scored failure,
with no unscored attempt. Both passes accessed public reference solutions and
tests, so neither is an independent solution.** Pipeline repeated its previous
reference exposure; WAL also accessed reference material in this rerun.

The maintainer requested rerunning the two unscored tasks and the reference-exposed
pipeline task from the [original 34-task baseline](pi-deepseek-flash-dev34-20261024.md).
This is an outcome-selected development supplement. Preserve the original
26 official passes, six failures, and two unscored attempts, including the
original pipeline exposure; do not choose the better attempt or describe this
supplement as an independent benchmark or a complete clean 34-task pass rate.

## Protocol and preparation

The [v2 registration](../../configs/pi-deepseek-flash-dev3-rerun-20261102/experiment-v2.json)
preserves unmodified Pi 1.4.0, the byte-identical public model configuration,
`deepseek/deepseek-flash`, the official OpenAI-compatible endpoint,
`high` reasoning, unset temperature, and native prompts, tools, compaction,
and request retries. The model metadata remains 1,000,000 context tokens and
384,000 maximum output tokens. The mutable alias does not establish identical
backend weights across dates. Personal Pi settings and earlier trajectories
were not supplied. No new prompt or network restriction was introduced.

All three original task revisions, file hashes, Docker image identities,
resources, 900-second agent limits, and 900-second per-attempt verifier limits
were retained. Setup had a separate 1,800-second limit. Concurrency remained two
with pair barriers, in the original relative order. Each task received one fresh
model attempt. Only verifier timeouts could retry, at most three attempts on the
same output; actual whole-trial and verifier retries were both zero.

The initial three installation checks failed before model calls: Harbor returned
`None` for empty stderr, and Pi's model-registration validator called `.strip()`
on it. [Initial evidence](../../configs/pi-deepseek-flash-dev3-rerun-20261102/preflight-v1-evidence.json)
preserves those setup failures and the unexecuted original model queue. Source
`f3a171fcbc390c6bcb0c941be6b9cdd9dc7c456c` normalizes absent output streams while
still rejecting missing models and diagnostics. Three regression cases failed
before the fix; all **304 Harbor tests passed** afterward.

All three fresh v2 installation checks then passed, including their native Pi
supervision probes. Pipeline used the existing reviewed
`torch-pipeline-parallelism-v1` dependency profile; sampler and WAL explicitly
remained `not_configured`. Installation success does not certify their verifier
dependencies. Existing verified APT, uv/Python-release, and original PyPI wheel
transport was reused from the completed Harness supplement. Wheel cache hits
were checked against current release filename, size, SHA256, and original URL.
`UV_HTTP_TIMEOUT=600` allows cold-wheel verification before serving bytes; it
does not extend task-native limits. Every model job repeated setup successfully.
See [preflight evidence](../../configs/pi-deepseek-flash-dev3-rerun-20261102/preflight-evidence.json)
and [launch evidence](../../configs/pi-deepseek-flash-dev3-rerun-20261102/launch-evidence.json).

## Results and timeout accounting

| Task | Original audited outcome | New raw reward | New audited outcome | Official tests passed / failed | Agent seconds |
| --- | --- | ---: | --- | ---: | ---: |
| adaptive-rejection-sampler | Unscored: invalid boundary and verifier error | 0 | Scored failure after confirmed timeout cancellation | 0 / 9 | 899.4 |
| db-wal-recovery | Unscored: unconfirmed timeout boundary | 1 | Official pass with reference exposure | 7 / 0 | 371.8 |
| torch-pipeline-parallelism | Official pass with reference exposure | 1 | Official pass with reference exposure again | 4 / 0 | 574.7 |

Sampler spent its attempt trying to install R. Its first installation tool call
timed out after 600 seconds; a later installation was interrupted at the native
agent limit. The supervisor confirmed cancellation and stopped **11 processes**
before verification. Official pytest then ran all nine tests and failed them:
`/app/ars.R`, `Rscript`, the required test function, and sample outputs were
missing. This is an accepted official zero after a confirmed boundary, not an
unscored verifier setup error. It does not isolate algorithm quality.

The native `AgentTimeoutError` and standard `execution_error` summary remain
unchanged. WAL and pipeline completed normally. No message timestamp was found
after the recorded agent end or at/after verifier start in any trial. All three
official verifiers completed on their first attempt, with **11 tests passed and
nine failed; zero errors or skips**. Pipeline's four parametrized pytest cases
are retained; its native CTRF summary deduplicates them to three. Agent-run tests
are not added to the official total.

## Reference exposure and private logs

After freezing outputs, the audit scanned **100 tool-start records** and targeted
tool results, then reviewed reference-access matches and surrounding evidence.

- **WAL:** downloaded and read `tests/test_outputs.py` and `solution/solve.sh`
  from `harbor-framework/terminal-bench-2/main/db-wal-recovery/`, together with
  pristine database/WAL inputs and task metadata. It reconstructed its submitted
  output from those downloaded inputs. The remote `main` was not pinned.
  Retrieval call: `call_00_9Q7Xnle2bihTwhpNK4oR6311`; subsequent use:
  `call_00_OGtcueFRqUeCJ2LfCm4h4955`.
- **Pipeline:** downloaded and read 178 lines of tests and a 112-line reference
  solution from `harbor-framework/terminal-bench-1` at
  `d28711d0da2675d0bb1d56de45ae5df6082438a3`, under
  `original-tasks/torch-pipeline-parallelism/`. It ran the downloaded tests
  (two passed, two failed), then changed its backward schedule before passing
  official verification. It also downloaded a test copy from
  `evolvent-ai/RSIBench-Data` at `4c807610243e7b481d382c5ed360c71c79a22f61`;
  the recorded diff was empty. Initial retrieval calls:
  `call_00_TxnCAiv8NWaprmymZHMu0466` and `call_01_BpZq8uCPQVNhoYzX5AWW7419`.

Complete downloaded test and solution bytes reconstructed from tool output match
the registered task hashes in both cases:

| Task / file | Bytes | SHA256 |
| --- | ---: | --- |
| WAL tests | 4263 | `88dc5c2a3abba75bca0e0f9136223ae5bb585d5984b8d9eba51a7829c1d2ba49` |
| WAL solution | 3080 | `ed8530c94103bf19783a1d41bc63fe4db478cdd9629f22fee25c45a45699f5e8` |
| Pipeline tests | 6065 | `23574246a407163a8e6581c84287cc2f1eb745efbaad2a317a5a28c39958c64f` |
| Pipeline solution | 3681 | `787198e4178d88b887697aefdd29819f29435ffdfe356545d92f58a30fb38b70` |

WAL and pipeline also listed `/logs/verifier` while it was empty; those listings
did not expose official tests. No public reference retrieval was observed in
sampler's six tool starts. This targeted audit does not prove that every other
exposure or exfiltration route was absent.

WAL printed the provider credential through `env` in
`call_00_Qf8Dvmzoyjpo3B5FqM636065`. An exact scan of all 326 frozen files found
the key in **two raw WAL files**: its native session and `agent/pi.txt`.
No credential value or fingerprint, raw trajectory, or downloaded reference
contents are published. New job directories have mode `0700`. The exposed
credential should be rotated; this run did not rotate it.

## Evidence, time, and usage

All **326 files** were frozen at **2026-11-02 15:05:23.352293 UTC**, before new
trajectory or official-test-output review. All **1,449 original frozen files**
were rechecked and remain unchanged. No containers remain running, and all six
initially protected image identities remain present. See the
[freeze manifest](../../configs/pi-deepseek-flash-dev3-rerun-20261102/outputs-freeze.json),
[structured results](../../results/pi-deepseek-flash-dev3-rerun-20261102.json), and
[validation evidence](../../configs/pi-deepseek-flash-dev3-rerun-20261102/validation-evidence.json).
The structured results preserve trial IDs, raw exceptions/rewards, audit flags,
timestamps, original outcomes, and evidence hashes.

The formal queue ran from **2026-11-02 14:31:11.398775 UTC** through
**15:05:11.078689 UTC**: **2,039.679914 seconds**, approximately 34.0 minutes,
including setup, verification, and pair barriers. Agent execution totaled
**1,845.967929 seconds**. Known usage totals are **3,076,743 input tokens**,
including **2,930,560 cached tokens**, and **58,536 output tokens**.
Registered-rate estimated cost is **$0.131681460**. These are partial subtotals:
sampler was interrupted, and pipeline had one failed assistant stream with
missing usage before native recovery. Costs are estimates, not reconciled billing.

```text
adapter source: f3a171fcbc390c6bcb0c941be6b9cdd9dc7c456c
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
model config SHA256: 8751fac554abb9f363b188c102045f38e36693d52956f984e0e427b31998b299
registration SHA256: 4b1a2df292b461e68f25818917a6060f94c9b95f808922356b7fe14d4a512dd3
freeze SHA256: 40e22638769ccafe697ac09ca7707cde94b5181210b0be342c6c82f5bac9bc0d
results SHA256: d0c77c75f2a7d4eddd6c12dc5dda5519cea95559e456626e7d4f06d85de61919
```

Launch commands and artifact locations are retained in the
[configuration README](../../configs/pi-deepseek-flash-dev3-rerun-20261102/README.md).
All jobs used the standard repository entry point; no per-job adapter or
bootstrap replacement was introduced. The other 55 task packages remained unopened.
