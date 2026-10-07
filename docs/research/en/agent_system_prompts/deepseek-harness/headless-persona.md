# DeepSeek Harness: headless persona fragment

> Analysis generated from the [Chinese source](../../../zh-CN/agent_system_prompts/deepseek-harness/headless-persona.md). This version preserves the upstream English original; the Chinese version contains its full translation. Tool names, paths, code identifiers, template placeholders, and machine-read format markers remain unchanged.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`
- [Original source](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/bundle/headless/cordis.patch.yml)
- Selector: `YAML config.personaPrefix folded scalar`
- Source file: [packages/bundle/headless/cordis.patch.yml](../../../../../references/deepseek-harness/packages/bundle/headless/cordis.patch.yml)
- Source file SHA256: `d0c99638f497c315e248ab63564fa27b4792c60506d6ab8f22c87018b64ab95d`
- Chinese translation SHA256: `55dbc7729b5bbd5c86479d0eb053b3342b04d133db1bf880d551b0738494649a`
- English original SHA256: `e0eb4484e48650627aa9a07bae720c151efc5c331e6e237ad9861e255ba00743`
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
