# Harbor adapter

[English](README.md) | [简体中文](README.zh-CN.md)

这个独立 workspace 包含 nanoPyCodeAgent 面向 Terminal-Bench 及其他 Harbor
评测任务的 adapter。它属于开发基础设施，不是面向普通用户的
`nanoPyCodeAgent` 软件包的一部分。该 workspace 的 lockfile 将 Harbor 固定在
0.21.0。

## 运行 benchmark

设置 CLI 使用的连接凭据。使用第三方或代理 endpoint 时，配置 API key 和 base
URL；模型由下方 Harbor 命令中的 `--model` 选择：

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_BASE_URL="https://gateway.example"
```

新的 benchmark 统一从仓库根目录通过标准入口运行：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/qemu-alpine-ssh.json
```

此示例固定了 QEMU 题目版本，模型为 `deepseek/deepseek-flash`。请配置对应的
endpoint 和凭证；测试其他模型或题目时，复制配置并修改 `agents[].model_name`、
题目选择及预算。这是普通的 Harbor JSON 配置，入口会补齐标准验证器和缓存策略。
入口接受本仓库的 `NanoPyCodeAgent` adapter 和预算参数，凭证通过环境变量传入。

入口会将当前工作区（包括未提交修改）构建为 wheel，并核对其 Python 源码与保存的
快照一致；同时保存 adapter 快照及源码、wheel 的哈希，整个运行都使用该快照。
输入和日志保存在 `jobs/<job-name>-input/`，Harbor 输出保存在
`jobs/<job-name>/`，不会覆盖已有运行。`summary.json` 记录评分、安装和预检状态、
缓存使用情况及验证次数。基础设施异常保留为无评分，不会转换为 0 分。
执行错误或结果不完整时命令返回非零退出码；正常完成验证得到 0 分仍是有效结果。

可用 `--job-name <unique-name>` 命名运行。`--prepare-only` 只构建并保存输入，
不启动容器；`--install-only` 只执行依赖安装和预检，不调用模型、不运行官方测试。
完整运行仍会在自己的新容器里执行安装和预检，不能把 install-only 容器续跑为解题。

### 依赖缓存与预检

标准 adapter 自动使用被 Git 忽略的 `.cache/nanopy-harbor/` 跨运行共享缓存，
可通过 `NANOPY_HARBOR_CACHE` 或入口的 `--cache-dir` 覆盖。对于 APT 系统，先更新
索引并解析 SHA256 下载计划，再恢复匹配的缓存文件、下载缺失文件。下载成功后会先
校验并保存缓存，再安装，避免 APT 清理钩子删除共享副本。版本或哈希不匹配时不会
复用旧包，文件损坏会在模型调用前终止安装。其他包管理器使用 Harbor 的常规安装。

历史下载只需导入一次：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter import-apt \
  /path/to/bootstrap-cache/manifest.json
```

manifest 是包含 `url`、`filename`、`size`、`sha256` 的 JSON 对象数组，同目录下
配套 `packages/<filename>` 文件。导入时逐个校验，使用时还必须独立匹配当前 APT
索引。也可将整个共享缓存复制到其他机器。新机器没有匹配缓存时仍依赖原下载地址
可用；此机制不会更换软件源或伪造缺失版本。

验证器依赖预检配置位于 `src/harbor_adapter/bootstrap.py`，绑定已检查的题目版本。
目前 QEMU 配置会安装 `sshpass`，并通过 `pytest --version` 预热原验证器所需的
uv 0.9.5、Python 3.13、pytest 8.4.1 和 pytest-json-ctrf 0.3.5，不执行题目断言或
参考解。未知的 QEMU 版本会在安装阶段报错，要求先检查对应预检配置；没有预检配置
的其他题目明确记录为 `not_configured`。其他题目需要预检时，在这里新增配置及回归测试。

每次安装都会写入 `agent/bootstrap.json`，失败时也保留已完成的步骤。预检失败会
在模型调用前终止 trial。官方验证脚本保持原样，执行时仍可能访问网络，所以预检
通过不能保证后续没有网络故障。完整标准运行默认启用下述验证超时重试，整题重试
次数为零。CI 会验证这些约定，不调用模型、不启动 Docker。

### 直接调用 Harbor

开发 adapter 或对照已发布版本时，仍可使用底层 Harbor 入口，并固定容器内 agent 版本：

```bash
uv run --project benchmarks/harbor harbor run \
  --task terminal-bench/openssl-selfsigned-cert \
  --agent harbor_adapter:NanoPyCodeAgent \
  --agent-kwarg git_ref=<commit-sha> \
  --model anthropic/claude-sonnet-4-6 \
  --verifier harbor_adapter:RetryingVerifier \
  --verifier-timeout-multiplier 4 \
  --env docker \
  --n-concurrent 1 \
  --n-attempts 1
```

如需安装已经发布到 PyPI 的版本，请使用
`--agent-kwarg version=<released-version>` 代替 `git_ref`。这两个版本参数互斥；
如果都未提供，adapter 会安装最新发布版本。为了让 benchmark 结果可复现，请始终
提供其中一个参数。`git_ref` 最好使用完整的 40 位 commit SHA；Harbor 可能把
`83e6271` 这样的无引号短 SHA 解析成数字。如果需要使用短 revision，请通过
`--agent-kwarg 'git_ref="83e6271"'` 保留其字符串类型。

adapter 通过 stdin 发送任务指令，在 task 容器的当前目录中运行 agent，并把合并后
的 stdout/stderr 保存到 `/logs/agent/nanopycodeagent.txt`。它默认沿用 CLI 的 50
轮限制；可以通过 `--agent-kwarg max_turns=20` 覆盖此设置。

可用 `--agent-kwarg time_budget_seconds=N` 限制解题时间，并在时间或轮数接近耗尽时
提醒模型收尾。预算应落在每题原生时限内，至少预留 30 秒费用补查时间，以及轨迹写入
和 harness 开销。例如，本轮原生 3600 秒的针对性实验使用 3420 秒；该值不能用于
900 秒题目。adapter 不会自动推导时间预算。

每次回复的生成上限可通过 `--agent-kwarg max_tokens=32768` 指定，它会转换为容器内的
`--max-tokens 32768`，优先于透传的 `ANTHROPIC_MAX_TOKENS` 环境变量。未指定时，
adapter 不添加该 flag，沿用已安装 agent 的环境变量／配置文件／默认值（引入该参数的
版本默认为 32768）。安装旧版本时需省略新参数。生效预算会记录到启动日志和 ATIF
trajectory 的 `agent.extra.max_tokens`。

adapter 还会要求 agent 将 ATIF-v1.7 trajectory 直接写入
`/logs/agent/trajectory.json`。Harbor 会把该文件作为 trial 的原生 ATIF 输出采集，
并将 prompt、completion、cache token 和 cost 汇总回填到 agent result。trajectory
缺失、无效或指标不完整时会保留明确诊断；未知 usage 或 cost 不会被记成零。
只要费用中包含估算，`final_metrics.extra` 就会记录 `cost_is_estimated: true`，
并通过 `estimated_cost_usd` 单独记录估算部分的金额。adapter 会将这两个字段保留到
agent result 的 `metadata.trajectory`，费用仅部分已知时也一样。带 generation ID
的估算费用仍会进行账单补查；补查成功后，真实费用会替换估算值。

默认情况下，adapter 会移除 `--model` 中的第一个 provider 前缀，并将结果作为
`ANTHROPIC_MODEL` 传给 nanoPyCodeAgent。只有自定义 endpoint 要求的实际模型名与
Harbor 的 `provider/model` 身份不同时，才显式设置 `ANTHROPIC_MODEL`；该覆盖值优先。
Harbor 原生的 provider 凭证和已经配置的 base URL 也会转换为 nanoPyCodeAgent SDK
所需的 `ANTHROPIC_*` 变量。

## 验证器超时重试

上面的示例使用 `harbor_adapter:RetryingVerifier`，适用于单阶段 Linux 题目。
原始测试脚本**总共最多执行 3 次**，仅当脚本超过题目原生的
`[verifier].timeout_sec` 时才重试。900 秒时限的题目，每次仍最多执行 900 秒。
验证完成后立即停止，包括得分为 0 的情况。脚本错误、评分缺失或格式错误、取消执行
都不会触发下一次尝试。

`--verifier-timeout-multiplier 4` 为 Harbor 外层时限预留 3 次尝试以及上传测试、
清理进程和收集日志的时间，不会延长每次测试脚本的时限。如果其他超时覆盖或上限
导致总时间不足，会报错。可用 `--verifier-kwarg max_attempts=2` 将总尝试次数设为
2 次，或用 `max_attempts=1` 只执行一次；不允许设置为超过 3 次。

重试复用同一容器、agent 产物和依赖缓存，agent 只运行一次。测试脚本需要能够在该
环境中重复执行，验证过程对文件系统的修改不会回滚。超时后会先终止测试进程组以及
同一 Linux session 中的其他进程，再开始下一次尝试。每次日志及评分文件归档到
`verifier/attempts/1/`、`2/`、`3/`。下一次尝试开始前会清理当前验证输出，避免旧
评分被误用。`verifier/retry-summary.json` 记录每次状态、耗时及可用的退出码。
所有尝试均超时后，仍以 Harbor 的 `VerifierTimeoutError` 结束。

容器需要 `python3` 和 `bash`，nanoPyCodeAgent adapter 会安装它们。这些选项用于
新运行，无法恢复旧 trial 已删除的容器或缺失的任务产物。Harbor 原生的
`--max-retries` 会重新执行整道题（包括 agent），与这里的验证尝试次数相互独立。

## 测试 adapter

```bash
uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml \
  benchmarks/harbor/tests
```
