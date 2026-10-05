# Pi：branch-summary

> 中文源文件；[英文版](../../../en/agent_system_prompts/pi/branch-summary.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- 定位：`TypeScript template literal BRANCH_SUMMARY_PROMPT`
- Source file: [packages/coding-agent/src/core/compaction/branch-summarization.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- Source file SHA256: `0279195d2cddfe99d4e42a1327d18c7f55ff15a8807d2c5d6cd465b2ab163011`
- Archived text SHA256: `76cf34f4204cc5465282460c9a3099301d9c8c0a672eda0e9d48ee7af422cec1`
- [Upstream license](../../../agent_system_prompts/licenses/pi.txt)

离开会话分支时的总结任务提示词。

分支切换/恢复路径，配合相同摘要系统消息。

## 内容方向

- 记录分支目标、限制、进展、决策和回到该分支后的下一步。

## 对 nanoPyCodeAgent 的启示

说明任务状态需要保留；不是主执行提示词必须增加的功能。

## 原文

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
