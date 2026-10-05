# Pi: branch-summary

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/pi/branch-summary.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [Original source](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- Selector: `TypeScript template literal BRANCH_SUMMARY_PROMPT`
- Source file: [packages/coding-agent/src/core/compaction/branch-summarization.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- Source file SHA256: `0279195d2cddfe99d4e42a1327d18c7f55ff15a8807d2c5d6cd465b2ab163011`
- Archived text SHA256: `76cf34f4204cc5465282460c9a3099301d9c8c0a672eda0e9d48ee7af422cec1`
- [Upstream license](../../../agent_system_prompts/licenses/pi.txt)

Task prompt for summarizing a departing conversation branch.

Branch navigation/resumption with the same summarization system message.

## Content directions

- Records the branch goal, constraints, progress, decisions, and next steps on return.

## Implications for nanoPyCodeAgent

Illustrates preserving task state, not a mandatory new feature for the main execution prompt.

## Original text

````text
Create a structured summary of this conversation branch for context when returning later.

Use this EXACT format:

## Goal
[What was the user trying to accomplish in this branch?]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Work that was started but not finished]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [What should happen next to continue this work]

Keep each section concise. Preserve exact file paths, function names, and error messages.
````
