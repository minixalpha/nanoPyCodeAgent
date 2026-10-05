# DeepSeek Harness: bash-result checking fragment

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/deepseek-harness/bash-result-check.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [Original source](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/shell/tool-bash/src/index.ts)
- Selector: `system-prompt section text literal`
- Source file: [packages/shell/tool-bash/src/index.ts](../../../../../references/deepseek-harness/packages/shell/tool-bash/src/index.ts)
- Source file SHA256: `53b18db95b1f2fc0bd82a5560756f8644ba8898197534b4915f96f7e3e450956`
- Archived text SHA256: `647bd85ba2e8c2a558ff8902caf03cf83f594bc35ac40ed905a10f61c73ec071`
- [Upstream license](../../../agent_system_prompts/licenses/deepseek-harness.txt)

System-prompt fragment registered by a tool plugin.

The tool-bash section registration; a tool-use convention rather than the entire agent policy.

## Content directions

- Inspect exit codes and investigate failures before proceeding.

## Implications for nanoPyCodeAgent

Directly useful for execution feedback. A successful exit code still does not establish that output meets requirements.

## Original text

````text
Check the [exit code: N] marker on every bash result; investigate failures before moving on.
````
