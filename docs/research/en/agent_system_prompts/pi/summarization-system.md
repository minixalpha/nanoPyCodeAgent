# Pi: summarization-system

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/pi/summarization-system.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [Original source](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/utils.ts)
- Selector: `TypeScript template literal SUMMARIZATION_SYSTEM_PROMPT`
- Source file: [packages/coding-agent/src/core/compaction/utils.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/utils.ts)
- Source file SHA256: `cc0baada8a2e31bcf1dbc18948c69ba2264fb2ad4d2c583ceb772fd3c3233674`
- Archived text SHA256: `c464889dcfa60441e642f291445b49523f263e6fb2725d0c25075543a2ec3f8f`
- [Upstream license](../../../agent_system_prompts/licenses/pi.txt)

Summarization-only system message.

Used by compaction and branch-summary requests.

## Content directions

- Summarize the conversation without answering its embedded questions or continuing the task.

## Implications for nanoPyCodeAgent

Keep roles distinct; ordinary task completion and summary-only output requirements should not be mixed.

## Original text

````text
You are a context summarization assistant. Your task is to read a conversation between a user and an AI assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary.
````
