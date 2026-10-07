# Codex：上下文压缩交接

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/codex/compaction.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`823ea830c0fd418b09ff02d36cad9a1fff66465b`
- [原始来源](https://github.com/openai/codex/blob/823ea830c0fd418b09ff02d36cad9a1fff66465b/codex-rs/prompts/templates/compact/prompt.md)
- 定位：`whole file`
- 来源文件: [codex-rs/prompts/templates/compact/prompt.md](../../../../../references/codex/codex-rs/prompts/templates/compact/prompt.md)
- 来源文件 SHA256: `ab0c334d4faca17e3afbb9b16967c1b2fdcc7242a9a0880af57949fa236d6d07`
- 中文译文 SHA256: `5fabc831dbc7279ec7044b75da55cd30e9100ddf1cec87c70d898de6ed9d70ec`
- 英文原文 SHA256: `ab0c334d4faca17e3afbb9b16967c1b2fdcc7242a9a0880af57949fa236d6d07`
- [上游许可证](../../../agent_system_prompts/licenses/codex.txt)

专用压缩提示词。

压缩请求使用；不是日常编码任务的系统正文。

## 内容方向

- 保留进展、决策、限制、偏好、后续步骤和关键引用。

## 对 nanoPyCodeAgent 的启示

可借鉴为长任务状态清单；当前没有压缩机制，复制这段文本不会自动获得上下文压缩能力。

## 中文译文

````text
你正在执行一次上下文检查点压缩。为将接手任务的另一个 LLM 创建交接摘要。

包含：
- 当前进展及已作出的关键决定
- 重要上下文、约束或用户偏好
- 尚需完成的工作与明确下一步
- 继续所需的关键数据、示例或参考

保持简洁、有结构，聚焦帮助下一个 LLM 无缝继续工作。

````
