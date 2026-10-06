# Pi：branch-summary

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/pi/branch-summary.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- 定位：`TypeScript template literal BRANCH_SUMMARY_PROMPT`
- 来源文件: [packages/coding-agent/src/core/compaction/branch-summarization.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- 来源文件 SHA256: `0279195d2cddfe99d4e42a1327d18c7f55ff15a8807d2c5d6cd465b2ab163011`
- 中文译文 SHA256: `d47dd94934492db52168f095d93675648637fe9b663adba53c3ab365591f05c3`
- 英文原文 SHA256: `76cf34f4204cc5465282460c9a3099301d9c8c0a672eda0e9d48ee7af422cec1`
- [上游许可证](../../../agent_system_prompts/licenses/pi.txt)

离开会话分支时的总结任务提示词。

分支切换/恢复路径，配合相同摘要系统消息。

## 内容方向

- 记录分支目标、限制、进展、决策和回到该分支后的下一步。

## 对 nanoPyCodeAgent 的启示

说明任务状态需要保留；不是主执行提示词必须增加的功能。

## 中文译文

摘要模板中的固定标题保留英文，以便与其输出格式协议对照。

````text
为这个对话分支生成结构化摘要，作为稍后返回时的上下文。

严格使用以下格式：

## Goal
[用户在此分支中想完成什么？]

## Constraints & Preferences
- [提到的约束、偏好或要求]
- [未提及时写“(none)”]

## Progress
### Done
- [x] [已完成任务或改动]

### In Progress
- [ ] [已开始但未完成的工作]

### Blocked
- [阻碍进度的问题，如有]

## Key Decisions
- **[决定]**：[简短理由]

## Next Steps
1. [继续这项工作应采取的后续行动]

各节保持简洁，精确保留文件路径、函数名和错误消息。
````
