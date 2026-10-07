# DeepSeek Harness：命令结果检查片段

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/deepseek-harness/bash-result-check.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [原始来源](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/shell/tool-bash/src/index.ts)
- 定位：`system-prompt section text literal`
- 来源文件: [packages/shell/tool-bash/src/index.ts](../../../../../references/deepseek-harness/packages/shell/tool-bash/src/index.ts)
- 来源文件 SHA256: `53b18db95b1f2fc0bd82a5560756f8644ba8898197534b4915f96f7e3e450956`
- 中文译文 SHA256: `ead441b6a2893e4cdcb38ae5b77a783ffa209403de9a2efee4bc5a60c2008303`
- 英文原文 SHA256: `647bd85ba2e8c2a558ff8902caf03cf83f594bc35ac40ed905a10f61c73ec071`
- [上游许可证](../../../agent_system_prompts/licenses/deepseek-harness.txt)

工具插件注册的系统提示词片段。

tool-bash 的 section 注册；属于工具操作约定，不是全部 agent 指导。

## 内容方向

- 每次检查退出码，失败后先调查原因再继续。

## 对 nanoPyCodeAgent 的启示

直接适合通用执行反馈。退出码成功仍不足以证明输出内容满足需求。

## 中文译文

````text
检查每次 bash 结果中的 [exit code: N] 标记，继续前先调查失败。
````
