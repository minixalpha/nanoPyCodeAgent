# 配置参考

[English](../en/configuration.md) | [简体中文](configuration.md) |
[用户文档](../README.md)

nanoPyCodeAgent 从进程环境中读取凭据、API endpoint 和模型。可选的用户级 settings
文件可以填补环境中缺失的值。

## 配置来源与优先级

优先级从高到低为:

1. nanoPyCodeAgent 进程中已经存在的环境变量。
2. `~/.nanoPyCodeAgent/settings.json` 的 `env` 对象。
3. 有内置默认值的设置使用其默认值。

Settings 文件只会填补环境中完全没有设置的键,绝不会替换已经存在的键。
nanoPyCodeAgent 不加载项目 `.env` 文件,没有项目级 settings 文件,也没有用于设置
凭据、endpoint 或模型的 CLI 选项。

Settings 文件在 Anthropic client 创建和模型选择之前加载,所以交互模式与 headless
模式遵循同一套优先级。

## 支持的设置

| 变量 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | 两种凭据至少提供一种 | 无 | Anthropic API key,或兼容的第三方服务接受的 API key。 |
| `ANTHROPIC_AUTH_TOKEN` | 两种凭据至少提供一种 | 无 | 需要以 `Authorization: Bearer` 认证的服务所使用的 bearer token,例如 OpenRouter 的 Anthropic-compatible endpoint。 |
| `ANTHROPIC_BASE_URL` | 否 | `https://api.anthropic.com` | Anthropic SDK 使用的 base URL。兼容的 proxy 或第三方 endpoint 需要设置此项;使用官方 API 时保持未设置。 |
| `ANTHROPIC_MODEL` | 否 | `claude-sonnet-4-6` | 每次 Messages API 调用所使用的模型。 |

`ANTHROPIC_API_KEY` 与 `ANTHROPIC_AUTH_TOKEN` 中至少要有一个提供可用凭据。两者都
不可用时,命令会在 stderr 报告缺少凭据,并在 Agent Run 启动前以状态 `1` 退出。

Settings 文件 loader 接受名称以 `ANTHROPIC_` 开头的任何键。上面的四个变量是
nanoPyCodeAgent 的配置契约;其他变量是否生效由安装的 Anthropic Python SDK 决定,
并可能随着该依赖变化。

## 环境变量

请在启动 agent 的 shell 中设置变量。使用官方 Anthropic API 时,最小配置如下:

```bash
export ANTHROPIC_API_KEY="your-api-key"
nanoPyCodeAgent
```

使用 Anthropic-compatible 服务时,请设置该服务要求的凭据形式、base URL 和它提供的
模型。例如:

```bash
export ANTHROPIC_AUTH_TOKEN="your-token"
export ANTHROPIC_BASE_URL="https://example.com/anthropic"
export ANTHROPIC_MODEL="provider/model-name"
nanoPyCodeAgent -p "run the test suite"
```

环境变量按照操作系统的一般规则继承。Agent 不会持久化这些变量。

## Settings 文件

可选 settings 文件使用固定的用户级路径:

```text
~/.nanoPyCodeAgent/settings.json
```

它必须是顶层为对象的 UTF-8 JSON。配置值放在 `env` 对象中;如果提供 `env`,它也
必须是对象。其结构与 [Claude Code settings](https://code.claude.com/docs/en/settings)
的 `env` 字段一致:

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_AUTH_TOKEN": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_MODEL": ""
  }
}
```

这些空字符串是占位符。请替换需要使用的值,其余项可以留空或删除。例如:

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "your-token",
    "ANTHROPIC_BASE_URL": "https://example.com/anthropic",
    "ANTHROPIC_MODEL": "provider/model-name"
  }
}
```

Settings 文件遵循以下规则:

- 文件不存在是正常情况,会被静默忽略。
- 缺少 `env` 字段时不会提供任何值。只读取 `env` 下的条目,其他顶层字段会被忽略。
- 只有以 `ANTHROPIC_` 开头的键符合条件,其他环境变量键会被忽略。
- 值必须是字符串,非字符串值会被忽略。
- Settings 文件中的值会去除首尾空白;空值与纯空白值会被忽略。
- 文件不可读、不是有效 UTF-8 或 JSON、顶层不是对象,或者 `env` 不是对象,都属于
  配置错误,会让启动过程因异常而停止。

Loader 不会强制文件权限。这个文件可能包含凭据,请将访问限制在当前用户,例如:

```bash
chmod 600 ~/.nanoPyCodeAgent/settings.json
```

## 空值与优先级

对于环境变量,“未设置”和“设置为空字符串”并不相同。Settings loader 根据键是否存在
来决定优先级:

| 环境状态 | Settings 文件中的值 | 结果 |
| --- | --- | --- |
| 键未设置 | 非空字符串 | 加载去除首尾空白后的 settings 文件值。 |
| 键未设置 | 空值、纯空白值或非字符串值 | 忽略该条目;如有内置默认值,可以继续使用默认值。 |
| 键存在且非空 | 任意值 | 环境变量胜出。 |
| 键存在但为空或纯空白 | 任意值 | 这个环境变量键仍会阻止 settings 文件值回填。 |

`ANTHROPIC_MODEL` 的最终环境值为空或纯空白时,会回退到
`claude-sonnet-4-6`。为空的 credential 或 base-URL 环境变量没有这种回退,可能导致
认证或请求失败。如果希望由 settings 文件提供值,请先 unset 空环境变量:

```bash
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL
```

## 优先级示例

假设文件内容如下:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://settings.example/v1",
    "ANTHROPIC_MODEL": "settings-model"
  }
}
```

同时环境中设置了:

```bash
export ANTHROPIC_MODEL="environment-model"
```

本次 run 会使用 `environment-model` 和 `https://settings.example/v1`:环境变量保留
model,settings 文件填补原本未设置的 base URL。

命令模式、选项、输出和退出状态请参阅 [CLI 参考](cli_reference.md)。
