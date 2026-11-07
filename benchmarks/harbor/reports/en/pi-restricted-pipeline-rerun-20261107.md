# Pi restricted Pipeline rerun — 2026-11-07

Pipeline passed the original official verifier: raw reward **1.0**, **4/4 pytest
cases passed**, and reviewed effective score **1.0**. No integrity violation was
observed in the frozen evidence. A broad local search for the task function
timed out without returning matches, so this finding does not certify that Pi
never attempted to locate reference material.

This is the single additional model attempt explicitly authorized on November 7
after the [November 5 collector failure](pi-restricted-pipeline-recovery-20261105.md).
That earlier completed model attempt remains unscored and unchanged. Across
these two restricted Pipeline model attempts, one has an official passing grade
and one remains an infrastructure error. No automatic whole-trial retry occurred.
The [earlier WAL result](pi-restricted-dev2-20261104.md) remains 7/7 passed with no
observed violation; WAL was not rerun here. Historical open-network violations
remain separate from this development follow-up.

## Registration and protocol

The [registration](../../configs/pi-restricted-pipeline-rerun-20261107/experiment.json)
pins source `ce8f346cee2fa340b3c1b1521df50bf62029a2a4`, including the repaired
UTF-8 chunk collector. Its SHA256 is
`8a07723be443c0aea8041cf0a2da4d8eb78c673e618d331b56da63d92d60e56b`.
Pi `1.4.0` uses the original distribution digest
`60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9`,
model `deepseek/deepseek-flash`, high reasoning, unset temperature, and model
metadata `maxTokens=384000`. The stock Pi loop has no injected turn cap.
The model alias is mutable; identical backend weights across dates are not claimed.

The original task revision is
`sha256:db605337c749a872cea7b5b413429b3915bb4c3efe0f7875f0c46ce81bd8c4fb`.
Its image, official scripts, and resources remain unchanged: 1 CPU, 8192 MiB RAM,
10240 MiB storage, and no GPU. Native limits remain 1800 seconds for setup,
900 seconds for the agent, and 900 seconds per verifier attempt. Only verifier
timeouts may retry, at most three total attempts on the same agent output.
This run used one verifier attempt and no retry.

The shared `restricted-v1` rules and external egress enforcement allow only
`api.deepseek.com` during model work. Positive API and negative public-network
controls passed. Verified dependency helpers run only during setup and official
verification; the setup helper was removed before model work, and verification
began after supervised agent completion. The original verifier shares the task
container. Local, DNS, and ICMP exemptions remain; this is not a claim that all
possible communication channels are absent.

## Results and dependency preparation

| Phase | Seconds | Outcome |
| --- | ---: | --- |
| Fresh install-only setup | 126.769297 | Dependency and network preflight passed; no model call |
| Formal setup | 450.814699 | Passed, including a slower APT index update |
| Model execution | 454.165559 | Normal completion; no collector error |
| Official verification | 312.179408 | Raw reward 1.0; first attempt passed |

The verifier subprocess took 309.392061 seconds; pytest itself reported
96.73 seconds. Native stdout lists four passed cases, including both parameterized
pipeline cases. The unchanged CTRF artifact reports three passed test-name
entries, with both pipeline parameters represented by one name. Both native
artifacts are preserved; the report does not rewrite their differing counts.

The [preflight evidence](../../configs/pi-restricted-pipeline-rerun-20261107/preflight-evidence.json)
records 45 wheels, 44 cache hits, and one fresh download. Formal setup records
45 wheel cache hits, totaling 3,080,595,097 verified bytes. Both setups also used
the two verified original uv/Python release archives without redirects. Official
verification required no wheel transfer. Filename, size, and SHA256 matched
current source metadata; task dependency commands were unchanged.

The [dependency comparison](../../configs/pi-restricted-pipeline-rerun-20261107/dependency-resolution-drift.json)
records 44 unchanged wheels and 62 unchanged APT packages relative to the earlier
preflight. The unpinned transitive dependency `regex` resolved from `2026.9.29`
to `2026.11.7`. Therefore this is not an identical resolved environment across dates.

Usage was 1,161,502 input tokens, including 1,133,952 cached tokens, and 43,244
output tokens across 36 usage records. Estimated cost is USD 0.066961512 using
the registered pricing. All usage records were present, and no assistant API
error was recorded; the estimate is not billing reconciliation.

## Integrity review and collector validation

The completed jobs were frozen before trajectory review. All 35 tool starts
and 35 results were accounted for, and tool arguments matched across native
events, the native session, and controller output. All 382 native events matched
the reconstructed controller stream exactly, including `agent_end` and
`agent_settled`. The largest JSON event was 296,980 bytes, exceeding the old
65,536-byte line limit without a collection error. This confirms the collector
fix on a fresh model run.

The [manual review](../../configs/pi-restricted-pipeline-rerun-20261107/review-coverage.json)
examined every tool-call argument, integrity-relevant results, generated code
and self-tests, supervision, official output, and network/cache boundaries:

- Pi read installed Transformers source, implemented `pipeline_parallel.py`,
  and tested it using locally generated models and data. An offline uv install
  failed; Pi then used existing dependencies through `PYTHONPATH`.
- Tool 9 searched `/usr`, `/opt`, and `/root` for the task function and AFAB
  terms. It timed out after 30 seconds with no returned matches. Broad filesystem
  searches and a process listing exposed current runtime metadata and supervisor
  command text. These are explicit local-search caveats.
- Tools 31–32 removed a docstring sentence mentioning hooks to avoid a possible
  naive static check. The reviewed submission contained no hook registration;
  hooks were confined to the agent's own self-test. No verifier was modified.
- No external reference fetch, hidden-test content, verifier interference, or
  retained watcher was observed. Both sidecar `bypass` diagnostics preceded
  model start and corresponded to controller negative probes. Named agent-period
  connection diagnostics showed only the API host; they are not exhaustive.
- Tool 4's filtered environment listing included the provider credential because
  `PI_` also matches `API_`. Three frozen logs contain it and remain private.
  Published artifacts contain hashes and credential-free summaries only.

The [hash-bound review](../../configs/pi-restricted-pipeline-rerun-20261107/integrity-review.json)
records `clear`, meaning no observed violation, not proof of exhaustive observation
or absence of training contamination. The
[reviewed audit](../../configs/pi-restricted-pipeline-rerun-20261107/integrity-audit.json)
has one eligible trial, zero pending reviews, zero observed violations, and
effective pass rate 1.0. Raw rewards and exceptions remain unchanged; an observed
violation would count as an effective zero without leaving the denominator.

## Evidence and validation

| Frozen job | Files | Freeze SHA256 |
| --- | ---: | --- |
| `pi-restricted-pipeline-install-20261107` | 15 | `8b2c39461aa146d5ccc2b29e5a01d640a157e1a28507af6fc3837e057572012d` |
| `pi-restricted-pipeline-model-20261107` | 33 | `46ccc20811d83e910d679e41133d666351d61a4eb8338c1d01702454d08935e6` |

The formal trial is `torch-pipeline-parallelism__HRsnb3D`. The
[freeze index](../../configs/pi-restricted-pipeline-rerun-20261107/outputs-freeze.json)
binds all 48 new files. All 446 earlier frozen files were also rechecked unchanged.
See the [model evidence](../../configs/pi-restricted-pipeline-rerun-20261107/model-evidence.json),
[structured results](../../results/pi-restricted-pipeline-rerun-20261107.json),
and [validation record](../../configs/pi-restricted-pipeline-rerun-20261107/validation-evidence.json).

No implementation changed for this rerun. The registered implementation had
410 passing tests, three skipped tests, and three separately enabled Docker
checks in the [prior validation](../../configs/pi-restricted-pipeline-recovery-v2-20261105/implementation-validation.json);
all three CI checks on the registered source succeeded. This change adds the
fresh preflight, official verifier result, integrity review, and synchronized
English/Chinese reports. Protected Docker images and preexisting stopped
containers were retained, and this run's containers were removed.
