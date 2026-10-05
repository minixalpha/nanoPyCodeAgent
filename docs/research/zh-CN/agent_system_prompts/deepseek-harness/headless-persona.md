# DeepSeek Harness：headless 身份片段

> 中文源文件；[英文版](../../../en/agent_system_prompts/deepseek-harness/headless-persona.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [原始来源](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/bundle/headless/cordis.patch.yml)
- 定位：`YAML config.personaPrefix folded scalar`
- Source file: [packages/bundle/headless/cordis.patch.yml](../../../../../references/deepseek-harness/packages/bundle/headless/cordis.patch.yml)
- Source file SHA256: `d0c99638f497c315e248ab63564fa27b4792c60506d6ab8f22c87018b64ab95d`
- Archived text SHA256: `e0eb4484e48650627aa9a07bae720c151efc5c331e6e237ad9861e255ba00743`
- [Upstream license](../../../agent_system_prompts/licenses/deepseek-harness.txt)

部署身份片段，保留 model 占位符。

headless bundle 配置 personaPrefix；SDK、ACP 和 Web 基础身份也使用相同句子。最终请求另有 harness 身份、工具段落及 cwd 后缀。

## 内容方向

- 只指定 agent 身份和模型；插件负责其他指导，身份句短不代表完整请求短。

## 对 nanoPyCodeAgent 的启示

把职责与工具合同分开，避免给核心提示词重复加入工具说明。不能从这句身份推断验证或规划能力。

## 原文

````text
You are a coding agent powered by the {{model}} model.
````
