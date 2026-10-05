# DeepSeek Harness: headless persona fragment

> Generated from the [Chinese source](../../../zh-CN/agent_system_prompts/deepseek-harness/headless-persona.md). Source blocks retain their original language; the analysis is not a line-by-line translation of the prompt.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [Original source](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/bundle/headless/cordis.patch.yml)
- Selector: `YAML config.personaPrefix folded scalar`
- Source file: [packages/bundle/headless/cordis.patch.yml](../../../../../references/deepseek-harness/packages/bundle/headless/cordis.patch.yml)
- Source file SHA256: `d0c99638f497c315e248ab63564fa27b4792c60506d6ab8f22c87018b64ab95d`
- Archived text SHA256: `e0eb4484e48650627aa9a07bae720c151efc5c331e6e237ad9861e255ba00743`
- [Upstream license](../../../agent_system_prompts/licenses/deepseek-harness.txt)

Deployment persona fragment retaining the model placeholder.

The headless bundle sets personaPrefix; SDK, ACP, and Web use the same base sentence. Final requests also contain harness identity, tool sections, and a cwd suffix.

## Content directions

- Specifies agent identity and model only; plugins provide further guidance, so a short persona does not imply a short complete request.

## Implications for nanoPyCodeAgent

Separate responsibilities from tool contracts and avoid repeating tool descriptions in the core. This persona alone does not establish verification or planning capabilities.

## Original text

````text
You are a coding agent powered by the {{model}} model.
````
