# Pi: checkpoint

> Analysis generated from the [Chinese source](../../../zh-CN/agent_system_prompts/pi/checkpoint.md). This version preserves the upstream English original; the Chinese version contains its full translation. Tool names, paths, code identifiers, template placeholders, and machine-read format markers remain unchanged.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [Original source](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/compaction.ts)
- Selector: `TypeScript template literal SUMMARIZATION_PROMPT`
- Source file: [packages/coding-agent/src/core/compaction/compaction.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/compaction.ts)
- Source file SHA256: `d5aebd41333957b57fa3f1bee2a18b3c00b5d47bb1b4af6f913cf8cd791099c8`
- Chinese translation SHA256: `d1d4c938525e60d05b8e3cf2e3abbeccd132508a802a26c5fad6f27d3175dfb4`
- English original SHA256: `9b00aa68df1a64279bc36e9093367f638701d48ec82e3d08436f65092a515f9b`
- [Upstream license](../../../agent_system_prompts/licenses/pi.txt)

Compaction task prompt, not the primary system prompt.

Works with summarization-system to create a context checkpoint.

## Content directions

- Tracks goals, user constraints, done/in-progress/blocked work, decisions, next steps, and critical context, preserving exact paths and errors.

## Implications for nanoPyCodeAgent

Reuse distinct completion states without imposing a long fixed plan or new tools on small tasks.

## Original text

Fixed headings in the summary template remain in English in the Chinese version so they can be compared with the output-format contract.

````text
The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages.
````
