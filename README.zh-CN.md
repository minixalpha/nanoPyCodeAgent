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

#### 运行某个分支或标签版本

直接从 GitHub 运行未发布的分支,或某个具体的发布标签:

```bash
# 分支上的最新提交
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@main" nanoPyCodeAgent

# 某个具体 tag
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@v0.1.0" nanoPyCodeAgent
```

### 如何更新

将已安装的工具升级到最新发布版:

```bash
uv tool upgrade nanoPyCodeAgent   # 或: pipx upgrade nanoPyCodeAgent
```
