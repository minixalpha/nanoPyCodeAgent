# DeepSeek Harness: bash-result checking fragment

> Analysis generated from the [Chinese source](../../../zh-CN/agent_system_prompts/deepseek-harness/bash-result-check.md). This version preserves the upstream English original; the Chinese version contains its full translation. Tool names, paths, code identifiers, template placeholders, and machine-read format markers remain unchanged.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [Original source](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/shell/tool-bash/src/index.ts)
- Selector: `system-prompt section text literal`
- Source file: [packages/shell/tool-bash/src/index.ts](../../../../../references/deepseek-harness/packages/shell/tool-bash/src/index.ts)
- Source file SHA256: `53b18db95b1f2fc0bd82a5560756f8644ba8898197534b4915f96f7e3e450956`
- Chinese translation SHA256: `ead441b6a2893e4cdcb38ae5b77a783ffa209403de9a2efee4bc5a60c2008303`
- English original SHA256: `647bd85ba2e8c2a558ff8902caf03cf83f594bc35ac40ed905a10f61c73ec071`
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
