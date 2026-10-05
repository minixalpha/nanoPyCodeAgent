# OpenCode：compaction

> 中文源文件；[英文版](../../../en/agent_system_prompts/opencode/compaction.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`907b3bc518fa48e90e8ec24dd327d13eee71c36c`
- [原始来源](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/agent/prompt/compaction.txt)
- 定位：`whole file`
- Source file: [packages/opencode/src/agent/prompt/compaction.txt](../../../../../references/opencode/packages/opencode/src/agent/prompt/compaction.txt)
- Source file SHA256: `552db0de0af1873a8acd4a631e2548345d4c43192de1d9be69c8feab4b41f80c`
- Archived text SHA256: `552db0de0af1873a8acd4a631e2548345d4c43192de1d9be69c8feab4b41f80c`
- [Upstream license](../../../agent_system_prompts/licenses/opencode.txt)

专用压缩代理系统提示词。

agent/agent.ts 的 compaction 配置；输出格式由用户消息提供。

## 内容方向

- 保留精确路径和标识、遵守摘要结构、只做交接而不继续对话。

## 对 nanoPyCodeAgent 的启示

保留未完成事项值得参考，但摘要能力不属于本次纯主提示词调整。

## 原文

````text
You are a context summarization agent. You are given a conversation between a user and an agent. Your goal is to produce a structured summary matching the format specified so another coding agent can continue the work.

Always follow the exact output structure requested by the user prompt. Keep every section, preserve exact file paths and identifiers when known, and prefer terse bullets over paragraphs.

Do not continue the conversation. Do not respond to any questions in the conversation. Only output the structured summary in the exact format requested by the user prompt. Respond in the same language as the conversation.
````
