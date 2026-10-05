# Pi：summarization-system

> 中文源文件；[英文版](../../../en/agent_system_prompts/pi/summarization-system.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/compaction/utils.ts)
- 定位：`TypeScript template literal SUMMARIZATION_SYSTEM_PROMPT`
- Source file: [packages/coding-agent/src/core/compaction/utils.ts](../../../../../references/pi/packages/coding-agent/src/core/compaction/utils.ts)
- Source file SHA256: `cc0baada8a2e31bcf1dbc18948c69ba2264fb2ad4d2c583ceb772fd3c3233674`
- Archived text SHA256: `c464889dcfa60441e642f291445b49523f263e6fb2725d0c25075543a2ec3f8f`
- [Upstream license](../../../agent_system_prompts/licenses/pi.txt)

摘要专用系统消息。

压缩与分支总结的请求使用。

## 内容方向

- 只总结对话，不回答被总结对话中的问题，不接着执行任务。

## 对 nanoPyCodeAgent 的启示

角色分工清楚；普通 agent 的完成要求与摘要模型的输出要求不能混用。

## 原文

````text
You are a context summarization assistant. Your task is to read a conversation between a user and an AI assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary.
````
