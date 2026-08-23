# Harbor adapter

[English](README.md) | [简体中文](README.zh-CN.md)

这个独立 workspace 包含 nanoPyCodeAgent 面向 Terminal-Bench 及其他 Harbor
评测任务的 adapter。它属于开发基础设施，不是面向普通用户的
`nanoPyCodeAgent` 软件包的一部分。该 workspace 的 lockfile 将 Harbor 固定在
0.21.0。

## 运行 benchmark

设置与 CLI 相同的 `ANTHROPIC_*` 环境变量。使用第三方或代理 endpoint 时，显式
设置以下三个变量：

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_BASE_URL="https://gateway.example"
export ANTHROPIC_MODEL="provider-model-name"
```

从仓库根目录通过这个 workspace 运行 Harbor，并固定安装到 task 容器中的 agent：

```bash
uv run --project benchmarks/harbor harbor run \
  --task terminal-bench/openssl-selfsigned-cert \
  --agent harbor_adapter:NanoPyCodeAgent \
  --agent-kwarg git_ref=<commit-sha> \
  --model anthropic/claude-sonnet-4-6 \
  --env docker \
  --n-concurrent 1 \
  --n-attempts 1
```

如需安装已经发布到 PyPI 的版本，请使用
`--agent-kwarg version=<released-version>` 代替 `git_ref`。这两个版本参数互斥；
如果都未提供，adapter 会安装最新发布版本。为了让 benchmark 结果可复现，请始终
提供其中一个参数。

adapter 通过 stdin 发送任务指令，在 task 容器的当前目录中运行 agent，并把合并后
的 stdout/stderr 保存到 `/logs/agent/nanopycodeagent.txt`。它默认沿用 CLI 的 50
轮限制；可以通过 `--agent-kwarg max_turns=20` 覆盖此设置。

`ANTHROPIC_MODEL` 的优先级高于 Harbor 的 `--model`。未设置该环境变量时，adapter
会移除 `--model` 中的第一个 provider 前缀。Harbor 原生的 provider 凭证和已经配置
的 base URL 也会转换为 nanoPyCodeAgent SDK 所需的 `ANTHROPIC_*` 变量。

## 测试 adapter

```bash
uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml \
  benchmarks/harbor/tests
```
