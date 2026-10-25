# Flash 1017 verifier-recovery supplement

**Completed:** one pass, one scored failure, and one unscored verifier error across three fresh agent trials. The merger passed all three tests in one verifier attempt. The CLI timed out once, then completed with five passing tests and one failing test (10 of 50 predictions wrong); valid zero stopped recovery after two attempts. Model recovery exhausted three 900-second verifier attempts downloading PyTorch/CUDA dependencies before pytest. Original baseline results remain unchanged. See the [English report](../../reports/en/dev34-flash1017-recovery-20261020.md), [complete Simplified Chinese report](../../reports/zh-CN/dev34-flash1017-recovery-20261020.md), and [audited results](../../results/dev34-flash1017-recovery-20261020.json). All three main containers and pre-verifier solution archives are retained; all 50 temporary image-cache relocations were restored and SHA256-verified.

This is a separately authorized three-task experiment, not a regrade or
replacement of the October 19 dev34 baseline. The original containers were
deleted and no `/app` solution artifacts were archived. The user explicitly
selected one new agent solution for each previously unscored task, with at most
three verifier attempts and retained workspaces.

## Frozen inputs

The [active plan](experiment-v2.json) fixes `multi-source-data-merger`,
`pytorch-model-cli`, and `pytorch-model-recovery` at the original task revisions.
The detached `jobs/runtime-source` checkout is
`40fdd041c370a96dc06f86b436eacc01ce1566d7`. Its core agent and 385-word prompt
are byte-identical to baseline main
`ce28b1e826a292d796ba64f13e79199b66f65758`; only the verifier harness gains an
explicit, tested collection-error recovery option. Each task uses the original
100-reply, 65,536-token-per-reply and 720-second work budget, 1,800-second setup
limit, original images/resources/package sources/tests, and 900-second verifier
attempt limit.

The model remains `deepseek/deepseek-flash` at
`https://api.deepseek.com/anthropic`. [Official documentation](https://api-docs.deepseek.com/quick_start/agent_integrations/)
checked on October 20 maps this mutable API alias to DeepSeek-V4.1-Flash-1017.
Temperature and reasoning effort remain unset.

## Execution and retention

Run fresh installation-only checks before the model phase. All three tasks have
no registered verifier dependency profile and must report `not_configured`;
installation success does not certify their verifier dependencies.

```bash
python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev34-flash1017-recovery-20261020/experiment-v2.json \
  --phase preflight
python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev34-flash1017-recovery-20261020/experiment-v2.json \
  --phase model
```

The existing orchestrator calls the standard Harbor entry point. It runs the
merger and CLI in the first pair, then model recovery, with maximum concurrency
two. Each model runs once. Both `retry_dependency_errors` and
`retry_collection_errors` are explicitly enabled. Timeout, recognized network
download failures before pytest, and aborted pytest collection share a maximum
of three attempts in the same container and with the same agent output. Any
valid scored pass or failure stops immediately. No solution repair, hidden-test
feedback, whole-trial retry, dependency substitution, or longer attempt deadline
is authorized by this registration.

Model runs set `environment.kwargs.keep_containers=true` as well as
`environment.delete=false`, and collect `/app` (plus `/data` for
the merger) before verification. Retain stopped containers, artifact manifests
and file hashes, input snapshots and all attempts. Original baseline records
remain immutable. Freeze all three new outputs before reviewing trajectories,
artifacts or official test contents. Report new outcomes separately, including
any remaining setup/verifier errors. Prior development exposure and the changed
recovery policy prevent interpreting this as a held-out or checkpoint-only
comparison.

The initial `experiment.json` ran installation-only checks. Before any model
call, the active v2 plan explicitly adds Docker `keep_containers=true`, because
Harbor 0.21 removes containers even with `delete=false` alone. Both registrations
and original configuration files remain intact; v2 accepts successful native
preflight records by hash and selects the corrected `*-retained.json` configs.
