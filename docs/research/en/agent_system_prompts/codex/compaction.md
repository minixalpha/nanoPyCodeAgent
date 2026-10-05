# Codex: context-compaction handoff

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/codex/compaction.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `823ea830c0fd418b09ff02d36cad9a1fff66465b`
- [Original source](https://github.com/openai/codex/blob/823ea830c0fd418b09ff02d36cad9a1fff66465b/codex-rs/prompts/templates/compact/prompt.md)
- Selector: `whole file`
- Source file: [codex-rs/prompts/templates/compact/prompt.md](../../../../../references/codex/codex-rs/prompts/templates/compact/prompt.md)
- Source file SHA256: `ab0c334d4faca17e3afbb9b16967c1b2fdcc7242a9a0880af57949fa236d6d07`
- Archived text SHA256: `ab0c334d4faca17e3afbb9b16967c1b2fdcc7242a9a0880af57949fa236d6d07`
- [Upstream license](../../../agent_system_prompts/licenses/codex.txt)

Specialized compaction prompt.

Used for compaction requests, not as the ordinary coding system body.

## Content directions

- Preserve progress, decisions, constraints, preferences, next steps, and critical references.

## Implications for nanoPyCodeAgent

Useful as a long-task state checklist; copying it does not create a compaction mechanism in the current agent.

## Original text

````text
You are performing a CONTEXT CHECKPOINT COMPACTION. Create a handoff summary for another LLM that will resume the task.

Include:
- Current progress and key decisions made
- Important context, constraints, or user preferences
- What remains to be done (clear next steps)
- Any critical data, examples, or references needed to continue

Be concise, structured, and focused on helping the next LLM seamlessly continue the work.
````
