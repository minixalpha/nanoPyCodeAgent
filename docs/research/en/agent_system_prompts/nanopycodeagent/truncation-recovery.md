# Injected truncation-recovery prompt

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/nanopycodeagent/truncation-recovery.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [Original source](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- Selector: `Python string expression _TRUNCATION_RECOVERY_NOTE`
- Source file: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- Source file SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- Archived text SHA256: `294ebbb8fa4b684d743867433c89e4f2242de950bc06201be798fe873d38acbd`

Complete string value at the current baseline; concatenations are resolved.

See uses of _TRUNCATION_RECOVERY_NOTE in agent.py.

## Content directions

- Continue from confirmed tool results and files without extending budgets; one recovery per run.

## Implications for nanoPyCodeAgent

Baseline for this study; runtime prompts remain unchanged and no new model experiment has run.

## Original text

````text
The previous response reached its output limit without finishing the task. No tool calls from that response were executed. Continue from the last confirmed tool results and current files within the remaining budget. This is the only automatic truncation recovery for this run.
````
