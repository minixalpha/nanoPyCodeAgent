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
```

任务在当前目录下执行,run 结束后命令随即退出。全部任务输入方式、选项、退出状态、
trajectory 输出和 Event Journal 行为请参阅[完整 CLI 参考](docs/user_docs/zh-CN/cli_reference.md)。

#### 运行某个分支或标签版本

直接从 GitHub 运行未发布的分支,或某个具体的发布标签:

```bash
# 分支上的最新提交
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@main" nanoPyCodeAgent

# 某个具体 tag
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@v0.1.0" nanoPyCodeAgent
```

### 配置

运行前请设置 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`。你也可以通过
环境变量或 `~/.nanoPyCodeAgent/settings.json` 配置 endpoint 与模型。支持的变量、
默认值、文件格式、优先级和空值处理请参阅[配置参考](docs/user_docs/zh-CN/configuration.md)。

### 如何更新

将已安装的工具升级到最新发布版:

```bash
uv tool upgrade nanoPyCodeAgent   # 或: pipx upgrade nanoPyCodeAgent
```

## 发布

维护者请参阅 [docs/RELEASING.md](docs/RELEASING.md) 了解发布流程与前置条件。
