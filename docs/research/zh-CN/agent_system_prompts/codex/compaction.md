# Codex：上下文压缩交接

> 中文源文件；[英文版](../../../en/agent_system_prompts/codex/compaction.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`823ea830c0fd418b09ff02d36cad9a1fff66465b`
- [原始来源](https://github.com/openai/codex/blob/823ea830c0fd418b09ff02d36cad9a1fff66465b/codex-rs/prompts/templates/compact/prompt.md)
- 定位：`whole file`
- Source file: [codex-rs/prompts/templates/compact/prompt.md](../../../../../references/codex/codex-rs/prompts/templates/compact/prompt.md)
- Source file SHA256: `ab0c334d4faca17e3afbb9b16967c1b2fdcc7242a9a0880af57949fa236d6d07`
- Archived text SHA256: `ab0c334d4faca17e3afbb9b16967c1b2fdcc7242a9a0880af57949fa236d6d07`
- [Upstream license](../../../agent_system_prompts/licenses/codex.txt)

专用压缩提示词。

压缩请求使用；不是日常编码任务的系统正文。

## 内容方向

- 保留进展、决策、限制、偏好、后续步骤和关键引用。

## 对 nanoPyCodeAgent 的启示

可借鉴为长任务状态清单；当前没有压缩机制，复制这段文本不会自动获得上下文压缩能力。

## 原文

````text
You are performing a CONTEXT CHECKPOINT COMPACTION. Create a handoff summary for another LLM that will resume the task.

Include:
- Current progress and key decisions made
- Important context, constraints, or user preferences
- What remains to be done (clear next steps)
- Any critical data, examples, or references needed to continue

Be concise, structured, and focused on helping the next LLM seamlessly continue the work.
````
