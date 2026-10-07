# Pi：checkpoint

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/pi/checkpoint.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/compaction.ts)
- 定位：`TypeScript template literal SUMMARIZATION_PROMPT`
- 来源文件: [packages/coding-agent/src/core/compaction/compaction.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/compaction.ts)
- 来源文件 SHA256: `d5aebd41333957b57fa3f1bee2a18b3c00b5d47bb1b4af6f913cf8cd791099c8`
- 中文译文 SHA256: `d1d4c938525e60d05b8e3cf2e3abbeccd132508a802a26c5fad6f27d3175dfb4`
- 英文原文 SHA256: `9b00aa68df1a64279bc36e9093367f638701d48ec82e3d08436f65092a515f9b`
- [上游许可证](../../../agent_system_prompts/licenses/pi.txt)

压缩请求的任务提示词，不是主系统提示词。

与 summarization-system 配合生成 context checkpoint。

## 内容方向

- 目标、用户限制、已完成/进行中/阻塞、决策、下一步和关键上下文，保留精确路径与错误。

## 对 nanoPyCodeAgent 的启示

可借鉴明确区分完成状态；无需为了小任务引入固定长计划或新工具。

## 中文译文

摘要模板中的固定标题保留英文，以便与其输出格式协议对照。

````text
以上消息是一段待总结的对话。创建结构化上下文检查点摘要，供另一个 LLM 继续工作。

严格使用以下格式：

## Goal
[用户想完成什么？会话涉及不同任务时，可列出多项。]

## Constraints & Preferences
- [用户提到的约束、偏好或要求]
- [未提及时写“(none)”]

## Progress
### Done
- [x] [已完成任务或改动]

### In Progress
- [ ] [当前工作]

### Blocked
- [阻碍进度的问题，如有]

## Key Decisions
- **[决定]**：[简短理由]

## Next Steps
1. [按顺序列出接下来应做的事项]

## Critical Context
- [继续工作所需的数据、示例或参考]
- [不适用时写“(none)”]

各节保持简洁，精确保留文件路径、函数名和错误消息。
````
