# DeepSeek official endpoint pilot20

Switched the 20-task pilot set from OpenRouter to DeepSeek's official
Anthropic-compatible endpoint and re-ran it with `deepseek-flash`. The run
scored **16/18 scored trials** (Harbor mean 0.80); two trials were lost to
infrastructure failures rather than model failures.

The complete configuration, per-trial usage, token-estimated cost, and balance
snapshots are in the
[public results](../results/tb21-deepseek-official-pilot20-20260930.json). Raw
evidence remains in the recorded Git-ignored `jobs/` directories.

## Configuration

| Setting | Value |
| --- | --- |
| Job | `tb21-deepseek-official-pilot20-20260930` |
| Agent | `e75cacb6` (`0.8.1.dev45`), locally built and verified wheel |
| Endpoint | `https://api.deepseek.com/anthropic` (Anthropic Messages) |
| Model | `deepseek-flash` |
| Tasks | the pinned 20-task pilot set |
| Budget | max_turns 100, max_tokens 65536, per-task agent budget native−180 s |
| Concurrency / attempts / retries | 2 / 1 / 0 |
| Provider pin / HTTP recorder | none — the provider is the only change |

## Result

| Bucket | Count |
| --- | ---: |
| Planned trials | 20 |
| Scored trials | 18 |
| Passed | 16 |
| Reward 0 | 2 |
| Infrastructure exceptions | 2 |
| Pass rate over scored | 88.9% |

- Reward 0: `torch-tensor-parallelism`, `pytorch-model-recovery`.
- `qemu-alpine-ssh`: agent setup failed fetching pinned Debian packages with
  HTTP 404; no model call happened.
- `torch-pipeline-parallelism`: the agent completed, but the official verifier
  exceeded its native 900 s limit.

Token usage: 30,933,108 prompt (30,586,240 cached, 346,868 uncached), 891,020
completion.

## Cost without a provider cost API

DeepSeek's official API reports token usage but no per-request cost, no
generation id, and no usage/billing endpoint — `usage.cost` is absent,
`x-generation-id` is absent, and `/v1/generation`, `/user/usage`,
`/billing/usage`, and `/pricing` all return 404. The previous OpenRouter
reconciliation path therefore cannot resolve a DeepSeek cost.

This branch adds a **token-based estimator** (see Implementation) that prices
the returned tokens with a static DeepSeek price list (USD per million:
input 0.3, cache read 0.006, cache write 0, output 1.2). It marks the result
`kind: estimated`, so it stays distinguishable from provider-reported cost.

| Component | Tokens | Rate | Cost (USD) |
| --- | ---: | ---: | ---: |
| Uncached input | 346,868 | 0.3 | 0.104060 |
| Cache read | 30,586,240 | 0.006 | 0.183517 |
| Output | 891,020 | 1.2 | 1.069224 |
| **Total** | | | **1.356802** |

An account balance delta (`/user/balance`, ¥106.63 → ¥102.01) is recorded as an
upper bound only: the interactive assistant session used the same account
during the run, so it is not an isolated run cost, and it is denominated in CNY.

## Implementation

- `cost.py`: add `estimated_cost(model, usage)` and a static DeepSeek price
  table; `agent.py` uses it only after `usage_cost` fails, so an explicit
  provider cost always wins.
- `harbor_adapter`: retry the system-dependency `apt-get` transaction once or
  twice on a transient HTTP 404 before failing setup. In the follow-up qemu
  re-run the retry fired on attempts 1/3 and 2/3, but the pinned
  `bullseye-security` index references `.deb` versions that are gone, so the 404
  is deterministic and a retry alone cannot fix that task. The historical fix
  preloads a verified `.deb` cache from the original APT index.

## Comparison limits

The OpenRouter pilot20 runs used provider pinning, a different snapshot date,
and different instrumentation, and this run has two infrastructure exceptions.
This is a provider-switch record, not a controlled causal comparison.
