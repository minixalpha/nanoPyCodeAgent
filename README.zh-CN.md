# nanoPyCodeAgent

[English](README.md) | [简体中文](README.zh-CN.md)

一个用纯 Python 构建的 Nano 级别的代码智能体。

> “凡我不能创造的,我便未能真正理解。” —— 理查德·费曼,1988

## 使用

nanoPyCodeAgent 需要 Python 3.13 或更高版本。

### 如何运行

有几种运行方式,任选其一即可。

#### 免安装运行

用 `uvx` 直接运行最新发布版,无需安装任何东西:

```bash
uvx nanoPyCodeAgent
```

#### 安装后运行

将它作为常驻命令行工具安装,之后可在任意位置运行:

```bash
uv tool install nanoPyCodeAgent   # 或: pipx install nanoPyCodeAgent
nanoPyCodeAgent
```

#### 一次性任务(非交互)

给它一个任务,它会自己做完退出——不给提示符,也不会停下来等确认,这正是脚本或
benchmark harness 需要的形态:

```bash
nanoPyCodeAgent -p "add a --version flag and run the tests"
nanoPyCodeAgent --prompt-file task.md
printf "%s" "$TASK" | nanoPyCodeAgent
```

任务在当前目录下执行。`--max-turns N` 限制一次运行最多花费多少轮模型回复(默认
50 轮)。

只要 agent 真的跑起来了,退出码就是 `0`——包括它放弃了、或者轮数用尽而任务没做
完,那该由检查结果的一方去判定。非零退出码表示这次运行根本没能进行:`1` 是缺少
凭据或 API 持续失败,`2` 是命令行用错了。

每次 Agent Run 还会在 `~/.nanoPyCodeAgent/journals/` 下写入可重放的内部 Event
Journal。这些 JSONL 文件可能包含提示词、模型回复、仓库内容和工具结果,应按敏感
数据处理;目录只允许当前用户访问(`0700`),每个文件的权限为 `0600`。Journal 既
不是公开 run output,也不是 trajectory,目前还不会自动轮转。

#### 运行某个分支或标签版本

直接从 GitHub 运行未发布的分支,或某个具体的发布标签:

```bash
# 分支上的最新提交
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@main" nanoPyCodeAgent

# 某个具体 tag
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@v0.1.0" nanoPyCodeAgent
```

### 配置

凭据与模型有两种配置来源:**环境变量**,以及可选的用户级配置文件
`~/.nanoPyCodeAgent/settings.json`。环境变量优先级更高——配置文件只用于填补你
未在环境变量中设置的键。

配置文件写法与 [Claude Code settings](https://code.claude.com/docs/en/settings)
一致:把值放在 `env` 对象下。空值或纯空白会被忽略。

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_MODEL": ""
  }
}
```

| 变量 | 是否必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | 是 | 无 | 你的 Anthropic API key,或第三方/代理服务的 key。 |
| `ANTHROPIC_BASE_URL` | 否 | `https://api.anthropic.com` | 将 SDK 指向非官方/代理 endpoint。使用官方 API 时保持不设置;留空值会导致请求失败。 |
| `ANTHROPIC_MODEL` | 否 | `claude-sonnet-4-6` | 覆盖默认模型。空值或纯空白会回退到默认值。 |

### 如何更新

将已安装的工具升级到最新发布版:

```bash
uv tool upgrade nanoPyCodeAgent   # 或: pipx upgrade nanoPyCodeAgent
```

## 发布

维护者请参阅 [docs/RELEASING.md](docs/RELEASING.md) 了解发布流程与前置条件。
