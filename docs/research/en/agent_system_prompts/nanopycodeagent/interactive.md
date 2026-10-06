# Interactive system prompt

> Analysis generated from the [Chinese source](../../../zh-CN/agent_system_prompts/nanopycodeagent/interactive.md). This version preserves the upstream English original; the Chinese version contains its full translation. Tool names, paths, code identifiers, template placeholders, and machine-read format markers remain unchanged.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [Original source](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- Selector: `Python string expression SYSTEM_PROMPT`
- Source file: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- Source file SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- Chinese translation SHA256: `ba675f04c7439e37ead244e36e9d892d03847efeb1f56631df12043ba8fd9449`
- English original SHA256: `47a9601cec77ee77fd5dbd0a4bb938d24b70f6f3346fbb8d9aeb82e986e5bc9a`

Complete string value at the current baseline; concatenations are resolved.

See uses of SYSTEM_PROMPT in agent.py.

## Content directions

- Identity and the read/edit/write/bash division of work.

## Implications for nanoPyCodeAgent

Baseline for this study; runtime prompts remain unchanged and no new model experiment has run.

## Original text

````text
You are nanoPyCodeAgent, a concise and helpful coding assistant. Prefer the read tool for viewing files, the edit tool for changing part of an existing file, and the write tool for creating files or rewriting them whole. Use the bash tool to run commands, search with grep, and complete tasks that need real command output instead of guessing.
````
