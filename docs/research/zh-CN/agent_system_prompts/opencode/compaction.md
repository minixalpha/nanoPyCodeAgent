# OpenCode：compaction

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/opencode/compaction.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`907b3bc518fa48e90e8ec24dd327d13eee71c36c`
- [原始来源](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/agent/prompt/compaction.txt)
- 定位：`whole file`
- 来源文件: [packages/opencode/src/agent/prompt/compaction.txt](../../../../../references/opencode/packages/opencode/src/agent/prompt/compaction.txt)
- 来源文件 SHA256: `552db0de0af1873a8acd4a631e2548345d4c43192de1d9be69c8feab4b41f80c`
- 中文译文 SHA256: `61f2a636cfb7225869b5e4dd6bd21aece8fdeab7eb8060564fac69df60e2f0f3`
- 英文原文 SHA256: `552db0de0af1873a8acd4a631e2548345d4c43192de1d9be69c8feab4b41f80c`
- [上游许可证](../../../agent_system_prompts/licenses/opencode.txt)

专用压缩代理系统提示词。

agent/agent.ts 的 compaction 配置；输出格式由用户消息提供。

## 内容方向

- 保留精确路径和标识、遵守摘要结构、只做交接而不继续对话。

## 对 nanoPyCodeAgent 的启示

保留未完成事项值得参考，但摘要能力不属于本次纯主提示词调整。

## 中文译文

````text
你是上下文摘要代理。输入是用户与代理的对话，目标是按指定格式生成结构化摘要，使另一个编码代理能够继续工作。

始终严格遵循用户提示要求的输出结构。保留每个小节，已知文件路径和标识符时精确保留，优先使用简练列表而非段落。

不要继续对话，也不要回答其中的问题。只按用户提示要求的准确格式输出结构化摘要。使用与对话相同的语言。

````
