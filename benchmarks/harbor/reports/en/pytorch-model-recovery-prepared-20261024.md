# PyTorch model recovery with separate dependency preparation

Date: 2026-10-24. This authorized continuation reuses the frozen
`pytorch-model-recovery__nCs7Y4H` solution from the
[October 20 supplement](dev34-flash1017-recovery-20261020.md), following the
[October 21 verifier continuation](pytorch-model-recovery-verifier-20261021.md).

**The retained solution passed all five official tests and received reward 1.0.**
Dependency preparation took 1,127.589 seconds, exceeding the original 900-second
limit. The unchanged official verifier then finished in 49.934 seconds within
its original 900-second limit. No model was called or solution regenerated.

| Phase | Independent limit | Actual duration | Outcome |
| --- | --- | --- | --- |
| Dependency preparation | 3,600 s | 1,127.589 s | Passed; dependencies installed, `pytest --version` succeeded |
| Official verification | 900 s | 49.934 s | Passed; reward 1.0; five tests passed |

The pytest session itself reported 5.00 seconds. The 49.934-second verifier
duration also includes the original script's APT refresh, uv installer, and
remaining dependency checks. Those steps were not removed or given extra time.
Preparation and formal verification each ran once. This was the seventh
verifier attempt on this solution; the previous six never reached pytest.

## Official test results

| Test | Result |
| --- | --- |
| `test_weights_file_unchanged` | Passed |
| `test_model_file_exists` | Passed |
| `test_model_loads_weights` | Passed |
| `test_state_dicts_match` | Passed |
| `test_model_loss` | Passed |

There were zero failed or skipped tests. Pytest emitted two non-failing warnings:
NumPy was unavailable, and the Transformer's layout did not enable nested-tensor
optimization. The dependency requirements were left unchanged.

## Preparation policy and implementation

The new `--dependency-timeout-sec 3600` option uses the reviewed
`pytorch-model-recovery-v1` profile for task revision
`sha256:2e628841cff93290919172398e573e794f34c95d9382b7425adde4364022decc`.
It checks the registered task configuration and test-script hashes, uses the
original uv 0.9.5 installer, Python 3.13, pytest 8.4.1, torch 2.7.1, and
pytest-json-ctrf 0.3.5 requirements, and runs only `pytest --version` from `/tmp`.
It does not import the submitted model or execute task assertions.

A failed preparation would have been recorded as a setup failure with no score
and no official verification. Successful preparation starts a separate native
verifier deadline; the 3,600-second budget cannot extend that deadline. The
original task image, resources, package sources, and official scripts were
preserved. The native test log reports Python 3.13.12, pytest 8.4.1, pluggy 1.7.0,
and pytest-json-ctrf 0.3.5.

The executed implementation was commit
`f7383dd69cec928ce61e12c49f3850c2edb34be5`. Original model generation used core
agent `ce28b1e826a292d796ba64f13e79199b66f65758` and runtime
`40fdd041c370a96dc06f86b436eacc01ce1566d7`. The frozen `/app/model.pt` SHA256 is
still `098642cbf41010a7fab7a9cf32995b49300cc3ccb1d724e7d57d729330f0bb4e`.

## Integrity and comparison limits

The same retained container and solution were used. Frozen solution and test
hashes passed checks before and after execution, and original trial files were
restored byte for byte. All three project containers are stopped and retained,
with unchanged identities and no container OOM flag. All 50 temporarily relocated
duplicate image-cache files were restored and SHA256-verified. The completed
dependency environment is retained. The local Harbor suite passed **209 tests**,
including independent deadlines, failed-preparation gating, and evidence
restoration.

This preparation policy changes the evaluation setup. Live dependency resolution
and cache state also limit comparisons. The October 19 baseline remains
**26 passes, five scored failures, three unscored verifier errors**. The October
20 and October 21 records remain unchanged. This passed continuation is recorded
separately; it does not replace earlier results or create a composite dev34 score.
New model calls and model cost were both zero.

- [Machine-readable result](../../results/pytorch-model-recovery-prepared-20261024.json)
- [Registered preparation and verification plan](../../configs/pytorch-model-recovery-prepared-20261024.json)
- Local evidence: `jobs/pytorch-model-recovery-prepared-20261024/`, including
  separate preparation/verifier logs, CTRF test results, executed sources,
  source and artifact hashes, integrity checks, and container retention.
- Live canonical verifier logs can refer to the original trial before and after
  the new batch; the separately archived batch logs determine this result.
- [Complete Simplified Chinese version](../zh-CN/pytorch-model-recovery-prepared-20261024.md)
