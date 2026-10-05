# OpenCode: compaction

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/opencode/compaction.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `907b3bc518fa48e90e8ec24dd327d13eee71c36c`
- [Original source](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/agent/prompt/compaction.txt)
- Selector: `whole file`
- Source file: [packages/opencode/src/agent/prompt/compaction.txt](../../../../../references/opencode/packages/opencode/src/agent/prompt/compaction.txt)
- Source file SHA256: `552db0de0af1873a8acd4a631e2548345d4c43192de1d9be69c8feab4b41f80c`
- Archived text SHA256: `552db0de0af1873a8acd4a631e2548345d4c43192de1d9be69c8feab4b41f80c`
- [Upstream license](../../../agent_system_prompts/licenses/opencode.txt)

Specialized compaction-agent system prompt.

The compaction entry in agent/agent.ts; the user message supplies the output format.

## Content directions

- Preserve exact paths and identifiers, follow summary structure, and hand off without continuing the conversation.

## Implications for nanoPyCodeAgent

Preserving unfinished work is useful, but implementing summarization is outside a main-prompt-only change.

## Original text

````text
You are a context summarization agent. You are given a conversation between a user and an agent. Your goal is to produce a structured summary matching the format specified so another coding agent can continue the work.

Always follow the exact output structure requested by the user prompt. Keep every section, preserve exact file paths and identifiers when known, and prefer terse bullets over paragraphs.

Do not continue the conversation. Do not respond to any questions in the conversation. Only output the structured summary in the exact format requested by the user prompt. Respond in the same language as the conversation.
````
