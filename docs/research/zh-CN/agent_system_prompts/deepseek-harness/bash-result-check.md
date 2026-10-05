# DeepSeek Harness：命令结果检查片段

> 中文源文件；[英文版](../../../en/agent_system_prompts/deepseek-harness/bash-result-check.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [原始来源](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/shell/tool-bash/src/index.ts)
- 定位：`system-prompt section text literal`
- Source file: [packages/shell/tool-bash/src/index.ts](../../../../../references/deepseek-harness/packages/shell/tool-bash/src/index.ts)
- Source file SHA256: `53b18db95b1f2fc0bd82a5560756f8644ba8898197534b4915f96f7e3e450956`
- Archived text SHA256: `647bd85ba2e8c2a558ff8902caf03cf83f594bc35ac40ed905a10f61c73ec071`
- [Upstream license](../../../agent_system_prompts/licenses/deepseek-harness.txt)

工具插件注册的系统提示词片段。

tool-bash 的 section 注册；属于工具操作约定，不是全部 agent 指导。

## 内容方向

- 每次检查退出码，失败后先调查原因再继续。

## 对 nanoPyCodeAgent 的启示

直接适合通用执行反馈。退出码成功仍不足以证明输出内容满足需求。

## 原文

````text
Check the [exit code: N] marker on every bash result; investigate failures before moving on.
````
