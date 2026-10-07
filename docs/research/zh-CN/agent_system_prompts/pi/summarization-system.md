# Pi：summarization-system

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/pi/summarization-system.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/utils.ts)
- 定位：`TypeScript template literal SUMMARIZATION_SYSTEM_PROMPT`
- 来源文件: [packages/coding-agent/src/core/compaction/utils.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/utils.ts)
- 来源文件 SHA256: `cc0baada8a2e31bcf1dbc18948c69ba2264fb2ad4d2c583ceb772fd3c3233674`
- 中文译文 SHA256: `c0a9d66b81c903f0c49be8bd31dbe8fda880ee1a5b4b53aa4d605973a5dfa6ed`
- 英文原文 SHA256: `c464889dcfa60441e642f291445b49523f263e6fb2725d0c25075543a2ec3f8f`
- [上游许可证](../../../agent_system_prompts/licenses/pi.txt)

摘要专用系统消息。

压缩与分支总结的请求使用。

## 内容方向

- 只总结对话，不回答被总结对话中的问题，不接着执行任务。

## 对 nanoPyCodeAgent 的启示

角色分工清楚；普通 agent 的完成要求与摘要模型的输出要求不能混用。

## 中文译文

````text
你是上下文摘要助手。任务是阅读用户与 AI 助手之间的对话，然后严格按指定格式生成结构化摘要。

不要继续对话，不要回答对话中的任何问题，只输出结构化摘要。
````
