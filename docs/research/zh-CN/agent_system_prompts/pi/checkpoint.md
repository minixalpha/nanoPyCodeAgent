# Pi：checkpoint

> 中文源文件；[英文版](../../../en/agent_system_prompts/pi/checkpoint.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/compaction.ts)
- 定位：`TypeScript template literal SUMMARIZATION_PROMPT`
- Source file: [packages/coding-agent/src/core/compaction/compaction.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/compaction.ts)
- Source file SHA256: `d5aebd41333957b57fa3f1bee2a18b3c00b5d47bb1b4af6f913cf8cd791099c8`
- Archived text SHA256: `9b00aa68df1a64279bc36e9093367f638701d48ec82e3d08436f65092a515f9b`
- [Upstream license](../../../agent_system_prompts/licenses/pi.txt)

压缩请求的任务提示词，不是主系统提示词。

与 summarization-system 配合生成 context checkpoint。

## 内容方向

- 目标、用户限制、已完成/进行中/阻塞、决策、下一步和关键上下文，保留精确路径与错误。

## 对 nanoPyCodeAgent 的启示

可借鉴明确区分完成状态；无需为了小任务引入固定长计划或新工具。

## 原文

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
